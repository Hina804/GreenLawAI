"""
Chat Manager
Manages conversation history for multi-turn dialogues.
"""

from typing import List, Dict, Literal
from dataclasses import dataclass, asdict
from datetime import datetime
import json


@dataclass
class Message:
    """Single message in conversation."""
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: str
    
    @classmethod
    def create(cls, role: str, content: str) -> 'Message':
        """Create message with current timestamp."""
        return cls(
            role=role,
            content=content,
            timestamp=datetime.now().isoformat()
        )


class ChatManager:
    """
    Manages conversation history and context.
    """
    
    def __init__(
        self,
        max_history: int = 10,
        max_tokens: int = 2000,
        token_estimator=None
    ):
        """
        Initialize chat manager.
        
        Args:
            max_history: Maximum number of messages to keep
            max_tokens: Maximum tokens for history context
            token_estimator: Function to estimate tokens (uses simple estimate if None)
        """
        self.max_history = max_history
        self.max_tokens = max_tokens
        self.token_estimator = token_estimator or self._simple_token_estimate
        
        self.messages: List[Message] = []
    
    def _simple_token_estimate(self, text: str) -> int:
        """Simple token estimation (4 chars ≈ 1 token)."""
        return len(text) // 4
    
    def add_message(self, role: str, content: str):
        """
        Add message to history.
        
        Args:
            role: Message role (user, assistant, system)
            content: Message content
        """
        message = Message.create(role, content)
        self.messages.append(message)
        
        # Trim if exceeds max_history
        if len(self.messages) > self.max_history:
            self.messages = self.messages[-self.max_history:]
    
    def get_history(self, include_system: bool = False) -> List[Dict]:
        """
        Get conversation history.
        
        Args:
            include_system: Include system messages
        
        Returns:
            List of message dictionaries
        """
        messages = self.messages
        
        if not include_system:
            messages = [m for m in messages if m.role != "system"]
        
        # Trim by token count
        total_tokens = 0
        trimmed = []
        
        for message in reversed(messages):
            tokens = self.token_estimator(message.content)
            if total_tokens + tokens > self.max_tokens:
                break
            trimmed.insert(0, message)
            total_tokens += tokens
        
        return [asdict(m) for m in trimmed]
    
    def get_context_string(self) -> str:
        """
        Get history as formatted string.
        
        Returns:
            Formatted conversation history
        """
        history = self.get_history()
        
        if not history:
            return ""
        
        lines = []
        for msg in history:
            role = msg['role'].capitalize()
            content = msg['content']
            lines.append(f"{role}: {content}")
        
        return "\n\n".join(lines)
    
    def clear(self):
        """Clear conversation history."""
        self.messages = []
    
    def save(self, filepath: str):
        """
        Save conversation to JSON file.
        
        Args:
            filepath: Output file path
        """
        data = {
            'messages': [asdict(m) for m in self.messages],
            'config': {
                'max_history': self.max_history,
                'max_tokens': self.max_tokens
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        print(f"✓ Saved conversation to {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> 'ChatManager':
        """
        Load conversation from JSON file.
        
        Args:
            filepath: Input file path
        
        Returns:
            ChatManager instance with loaded history
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        config = data.get('config', {})
        manager = cls(
            max_history=config.get('max_history', 10),
            max_tokens=config.get('max_tokens', 2000)
        )
        
        # Load messages
        for msg_data in data.get('messages', []):
            manager.messages.append(Message(**msg_data))
        
        print(f"✓ Loaded conversation from {filepath}")
        return manager
    
    def get_stats(self) -> Dict:
        """
        Get conversation statistics.
        
        Returns:
            Statistics dictionary
        """
        total_tokens = sum(self.token_estimator(m.content) for m in self.messages)
        
        return {
            'total_messages': len(self.messages),
            'user_messages': sum(1 for m in self.messages if m.role == 'user'),
            'assistant_messages': sum(1 for m in self.messages if m.role == 'assistant'),
            'total_tokens': total_tokens,
            'avg_tokens_per_message': total_tokens / len(self.messages) if self.messages else 0
        }


if __name__ == "__main__":
    # Test
    chat = ChatManager(max_history=5)
    
    chat.add_message("user", "What are the powers of a Forest Officer?")
    chat.add_message("assistant", "According to Section 26...")
    chat.add_message("user", "Can they arrest someone?")
    chat.add_message("assistant", "Yes, under certain conditions...")
    
    print("History:")
    print(chat.get_context_string())
    
    print("\nStats:")
    print(chat.get_stats())
    
    chat.save("test_conversation.json")
