"""
conversation_context.py

ASTRA Context Management System

Responsibilities:
- Build conversation context
- Retrieve recent chats
- Retrieve memory summaries
- Retrieve analytics summaries
- Assemble LLM-ready prompts
- Limit context growth

Future Ready:
- document_rag.py
- knowledge_graph.py
- vector memory
- local LLM routing
"""

from datetime import datetime

from memory_router import (
    get_context
)

from analytics_memory import (
    analytics_memory
)


class ConversationContext:

    def __init__(self):

        self.max_recent_messages = 10
        self.max_context_chars = 12000

    # ==================================================
    # RECENT CHAT
    # ==================================================

    def get_recent_chat(self):

        try:

            context = get_context(
                self.max_recent_messages
            )

            if isinstance(context, dict):

                return context.get(
                    "recent_chat",
                    []
                )

            return []

        except Exception:

            return []

    # ==================================================
    # ANALYTICS CONTEXT
    # ==================================================

    def get_analytics_context(
        self,
        filepath=None
    ):

        if not filepath:

            return None

        try:

            return analytics_memory.get_summary(
                filepath
            )

        except Exception:

            return None

    # ==================================================
    # CHAT FORMATTING
    # ==================================================

    def format_chat_history(
        self,
        chat_history
    ):

        if not chat_history:

            return ""

        lines = []

        for item in chat_history:

            if isinstance(item, dict):

                role = item.get(
                    "role",
                    "unknown"
                )

                content = item.get(
                    "content",
                    ""
                )

                lines.append(
                    f"{role}: {content}"
                )

            else:

                lines.append(
                    str(item)
                )

        return "\n".join(lines)

    # ==================================================
    # ANALYTICS FORMATTING
    # ==================================================

    def format_analytics(
        self,
        analytics
    ):

        if analytics is None:

            return ""

        return str(analytics)

    # ==================================================
    # MEMORY SUMMARY
    # ==================================================

    def build_memory_section(
        self,
        filepath=None
    ):

        analytics = (
            self.get_analytics_context(
                filepath
            )
        )

        if analytics is None:

            return ""

        return (
            "\n=== ANALYTICS MEMORY ===\n"
            f"{analytics}\n"
        )

    # ==================================================
    # CONVERSATION SECTION
    # ==================================================

    def build_chat_section(self):

        chat = self.get_recent_chat()

        formatted = (
            self.format_chat_history(
                chat
            )
        )

        if not formatted:

            return ""

        return (
            "\n=== RECENT CHAT ===\n"
            f"{formatted}\n"
        )

    # ==================================================
    # SYSTEM SECTION
    # ==================================================

    def build_system_section(self):

        timestamp = (
            datetime.now()
            .isoformat()
        )

        return (
            "\n=== SYSTEM ===\n"
            f"Timestamp: {timestamp}\n"
            "Assistant: ASTRA\n"
        )

    # ==================================================
    # BUILD RAW CONTEXT
    # ==================================================

    def build_context(
        self,
        user_input,
        filepath=None
    ):

        return {

            "user_input":
                user_input,

            "recent_chat":
                self.get_recent_chat(),

            "analytics":
                self.get_analytics_context(
                    filepath
                ),

            "timestamp":
                datetime.now().isoformat()
        }

    # ==================================================
    # BUILD LLM PROMPT
    # ==================================================

    def build_prompt_context(
        self,
        user_input,
        filepath=None
    ):

        sections = [

            self.build_system_section(),

            self.build_chat_section(),

            self.build_memory_section(
                filepath
            ),

            "\n=== USER REQUEST ===\n"
            f"{user_input}\n"
        ]

        prompt = "\n".join(sections)

        return self.limit_context(
            prompt
        )

    # ==================================================
    # CONTEXT LIMITER
    # ==================================================

    def limit_context(
        self,
        text
    ):

        if len(text) <= self.max_context_chars:

            return text

        return text[
            -self.max_context_chars:
        ]

    # ==================================================
    # CONTEXT STATS
    # ==================================================

    def stats(
        self,
        filepath=None
    ):

        recent_chat = (
            self.get_recent_chat()
        )

        analytics = (
            self.get_analytics_context(
                filepath
            )
        )

        return {

            "recent_messages":
                len(recent_chat),

            "analytics_loaded":
                analytics is not None,

            "max_context_chars":
                self.max_context_chars
        }

    # ==================================================
    # DEBUG
    # ==================================================

    def preview(
        self,
        user_input,
        filepath=None
    ):

        return self.build_prompt_context(
            user_input,
            filepath
        )


# ======================================================
# GLOBAL INSTANCE
# ======================================================

conversation_context = (
    ConversationContext()
)


# ======================================================
# WRAPPER FUNCTIONS
# ======================================================

def build_context(
    user_input,
    filepath=None
):

    return (
        conversation_context
        .build_context(
            user_input,
            filepath
        )
    )


def build_prompt_context(
    user_input,
    filepath=None
):

    return (
        conversation_context
        .build_prompt_context(
            user_input,
            filepath
        )
    )


def context_stats(
    filepath=None
):

    return (
        conversation_context
        .stats(
            filepath
        )
    )


def preview_context(
    user_input,
    filepath=None
):

    return (
        conversation_context
        .preview(
            user_input,
            filepath
        )
    )
