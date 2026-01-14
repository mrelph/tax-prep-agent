"""Session management for tax agent modes."""

import uuid
from datetime import datetime

from tax_agent.config import get_config
from tax_agent.models.mode import AgentMode, ModeState, MODE_INFO
from tax_agent.storage.database import TaxDatabase


# Trigger words for auto-detecting mode from user input
PREP_TRIGGERS = [
    "/collect", "/find", "/analyze", "/optimize", "/documents",
    "upload", "w2", "1099", "document", "prepare", "deduction",
    "add document", "new document", "gather", "collect",
]

REVIEW_TRIGGERS = [
    "/review", "check my return", "review my", "amendment",
    "1040", "filed return", "errors in", "mistakes",
    "audit", "verify return", "check return",
]

PLANNING_TRIGGERS = [
    "/plan", "/planning", "retirement", "roth", "scenario",
    "next year", "what if", "future", "strategy",
    "tax planning", "long term", "optimize for",
    "401k", "ira", "rmd", "conversion",
]


class SessionManager:
    """Manages mode state and transitions for the tax agent."""

    def __init__(self, db: TaxDatabase, tax_year: int | None = None):
        """
        Initialize the session manager.

        Args:
            db: Database instance
            tax_year: Tax year for this session
        """
        self.db = db
        config = get_config()
        self.tax_year = tax_year or config.tax_year
        self._current_mode: AgentMode | None = None
        self._current_state: ModeState | None = None
        self._mode_switch_message: str | None = None

    @property
    def current_mode(self) -> AgentMode:
        """Get current mode, defaulting to PREP if not set."""
        if self._current_mode is None:
            # Try to load the most recently used mode
            states = self.db.get_all_session_states(self.tax_year)
            if states:
                self._current_mode = states[0].mode
                self._current_state = states[0]
            else:
                self._current_mode = AgentMode.PREP
        return self._current_mode

    @property
    def current_state(self) -> ModeState:
        """Get current mode state, creating if needed."""
        if self._current_state is None or self._current_state.mode != self.current_mode:
            self._current_state = self.load_state(self.current_mode)
        return self._current_state

    @property
    def mode_info(self) -> dict:
        """Get display info for current mode."""
        return MODE_INFO[self.current_mode]

    def pop_switch_message(self) -> str | None:
        """Get and clear any pending mode switch message."""
        msg = self._mode_switch_message
        self._mode_switch_message = None
        return msg

    def switch_mode(self, mode: AgentMode, silent: bool = False) -> ModeState:
        """
        Switch to a different mode, saving current state first.

        Args:
            mode: The mode to switch to
            silent: If True, don't set a switch message

        Returns:
            The ModeState for the new mode
        """
        if self._current_state is not None:
            # Save current state before switching
            self.save_state()

        old_mode = self._current_mode
        self._current_mode = mode
        self._current_state = self.load_state(mode)

        if not silent and old_mode != mode:
            info = MODE_INFO[mode]
            self._mode_switch_message = (
                f"Switched to **{info['name']}** mode\n"
                f"_{info['description']}_\n\n"
                f"Focus: {info['focus']}"
            )

        return self._current_state

    def detect_mode(self, user_input: str) -> AgentMode | None:
        """
        Auto-detect mode from user input.

        Args:
            user_input: The user's message

        Returns:
            Detected mode or None if no clear detection
        """
        input_lower = user_input.lower()

        # Check for explicit mode commands first (highest priority)
        if input_lower.startswith("/prep"):
            return AgentMode.PREP
        if input_lower.startswith("/review"):
            return AgentMode.REVIEW
        if input_lower.startswith("/plan"):
            return AgentMode.PLANNING
        if input_lower.startswith("/mode "):
            mode_arg = input_lower.split()[1] if len(input_lower.split()) > 1 else ""
            mode_map = {"prep": AgentMode.PREP, "review": AgentMode.REVIEW, "planning": AgentMode.PLANNING}
            return mode_map.get(mode_arg)

        # Count trigger matches for each mode
        prep_score = sum(1 for t in PREP_TRIGGERS if t in input_lower)
        review_score = sum(1 for t in REVIEW_TRIGGERS if t in input_lower)
        planning_score = sum(1 for t in PLANNING_TRIGGERS if t in input_lower)

        # Only auto-switch if there's a clear winner
        max_score = max(prep_score, review_score, planning_score)
        if max_score == 0:
            return None

        # Require at least 1 trigger match to auto-switch
        if prep_score == max_score and prep_score >= 1:
            return AgentMode.PREP
        if review_score == max_score and review_score >= 1:
            return AgentMode.REVIEW
        if planning_score == max_score and planning_score >= 1:
            return AgentMode.PLANNING

        return None

    def maybe_switch_mode(self, user_input: str) -> bool:
        """
        Check if user input suggests a mode switch and switch if so.

        Args:
            user_input: The user's message

        Returns:
            True if mode was switched
        """
        detected = self.detect_mode(user_input)
        if detected and detected != self.current_mode:
            self.switch_mode(detected)
            return True
        return False

    def get_mode_context(self) -> dict:
        """Get context data for current mode."""
        return self.current_state.context_data

    def update_context(self, key: str, value: any) -> None:
        """Update a context value for current mode."""
        self.current_state.update_context(key, value)
        self.save_state()

    def add_message(self, role: str, content: str) -> None:
        """Add a message to current mode's conversation history."""
        self.current_state.add_message(role, content)
        # Don't save immediately to avoid too many DB writes
        # Save will happen on mode switch or explicit save

    def save_state(self) -> None:
        """Persist current mode state to database."""
        if self._current_state is not None:
            self._current_state.updated_at = datetime.now()
            self.db.save_session_state(self._current_state)

    def load_state(self, mode: AgentMode) -> ModeState:
        """
        Load saved state for a mode, creating if it doesn't exist.

        Args:
            mode: The mode to load state for

        Returns:
            The ModeState for the mode
        """
        state = self.db.get_session_state(mode, self.tax_year)
        if state is None:
            # Create new state for this mode
            state = ModeState(
                id=str(uuid.uuid4()),
                mode=mode,
                tax_year=self.tax_year,
                context_data={},
                conversation_history=[],
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            self.db.save_session_state(state)
        return state

    def get_mode_summary(self) -> str:
        """Get a summary of the current mode and its state."""
        mode = self.current_mode
        info = MODE_INFO[mode]
        state = self.current_state

        lines = [
            f"**Mode:** {info['name']}",
            f"**Description:** {info['description']}",
            f"**Focus:** {info['focus']}",
            f"**Tax Year:** {self.tax_year}",
        ]

        # Add mode-specific context info
        context = state.context_data
        if mode == AgentMode.PREP:
            doc_count = context.get("documents_collected", 0)
            if doc_count:
                lines.append(f"**Documents Collected:** {doc_count}")
            if context.get("last_analysis"):
                lines.append(f"**Last Analysis:** {context['last_analysis']}")

        elif mode == AgentMode.REVIEW:
            if context.get("return_file"):
                lines.append(f"**Return File:** {context['return_file']}")
            findings = context.get("findings_count", 0)
            if findings:
                lines.append(f"**Findings:** {findings}")

        elif mode == AgentMode.PLANNING:
            scenarios = context.get("scenarios_analyzed", 0)
            if scenarios:
                lines.append(f"**Scenarios Analyzed:** {scenarios}")

        # Conversation history summary
        history = state.conversation_history
        if history:
            lines.append(f"**Conversation Messages:** {len(history)}")

        return "\n".join(lines)

    def clear_mode_state(self, mode: AgentMode | None = None) -> int:
        """
        Clear state for a specific mode or all modes.

        Args:
            mode: Mode to clear, or None for all modes

        Returns:
            Number of states cleared
        """
        count = self.db.clear_session_states(mode)
        if mode is None or mode == self._current_mode:
            self._current_state = None
        return count


# Convenience function
def get_session_manager(tax_year: int | None = None) -> SessionManager:
    """Get a session manager instance."""
    from tax_agent.storage.database import get_database
    return SessionManager(get_database(), tax_year)
