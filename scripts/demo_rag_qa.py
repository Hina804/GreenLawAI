"""
Demo RAG Q&A Application
Interactive CLI for legal question answering with cloud-based RAG.
"""

import sys
import os
from pathlib import Path
import yaml

# Force PyTorch for Transformers
os.environ["USE_TF"] = "0"
os.environ["USE_TORCH"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from rag.rag_pipeline import RAGPipeline
from rag.chat_manager import ChatManager


def print_banner():
    """Print application banner."""
    print("\n" + "="*70)
    print("  LEGAL AI ASSISTANT - Forestry Laws Q&A")
    print("  Powered by GraphRAG + LLM")
    print("="*70)


def print_help():
    """Print help message."""
    print("\nCommands:")
    print("  <question>  - Ask a question")
    print("  /history    - Show conversation history")
    print("  /clear      - Clear conversation history")
    print("  /save       - Save conversation to file")
    print("  /stats      - Show conversation statistics")
    print("  /help       - Show this help message")
    print("  /exit       - Exit application")


def main():
    """Main application loop."""
    print_banner()
    
    # Load configuration
    config_path = "config/rag_config.yaml"
    if not os.path.exists(config_path):
        print(f"\n❌ Configuration file not found: {config_path}")
        print("Please create config/rag_config.yaml")
        return
    
    print(f"\n📄 Loading configuration from {config_path}...")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize RAG pipeline
    try:
        print("\n🚀 Initializing RAG pipeline...")
        rag = RAGPipeline.from_config(config)
    except RuntimeError as e:
        print(f"\n❌ {e}")
        return
    except Exception as e:
        print(f"\n❌ Error initializing pipeline: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Initialize chat manager
    chat_config = config.get('chat', {})
    if chat_config.get('enable_history', True):
        chat = ChatManager(
            max_history=chat_config.get('max_history', 10),
            max_tokens=chat_config.get('max_history_tokens', 2000)
        )
        print("✓ Chat history enabled")
    else:
        chat = None
        print("⚠ Chat history disabled")
    
    print("\n" + "="*70)
    print("💬 Ready! Ask a question about forestry laws.")
    print("Type /help for commands or /exit to quit.")
    print("="*70)
    
    # Main loop
    while True:
        try:
            # Get user input
            user_input = input("\n🔍 You: ").strip()
            
            if not user_input:
                continue
            
            # Handle commands
            if user_input.startswith('/'):
                command = user_input.lower()
                
                if command == '/exit':
                    print("\n👋 Goodbye!")
                    break
                
                elif command == '/help':
                    print_help()
                
                elif command == '/history':
                    if chat:
                        history = chat.get_context_string()
                        if history:
                            print("\n📜 Conversation History:")
                            print("-" * 70)
                            print(history)
                        else:
                            print("\n⚠ No conversation history yet")
                    else:
                        print("\n⚠ Chat history is disabled")
                
                elif command == '/clear':
                    if chat:
                        chat.clear()
                        print("\n✓ Conversation history cleared")
                    else:
                        print("\n⚠ Chat history is disabled")
                
                elif command == '/save':
                    if chat:
                        filename = f"conversation_{chat.messages[0].timestamp[:10]}.json" if chat.messages else "conversation.json"
                        chat.save(filename)
                    else:
                        print("\n⚠ Chat history is disabled")
                
                elif command == '/stats':
                    if chat:
                        stats = chat.get_stats()
                        print("\n📊 Conversation Statistics:")
                        print(f"  Total messages: {stats['total_messages']}")
                        print(f"  User messages: {stats['user_messages']}")
                        print(f"  Assistant messages: {stats['assistant_messages']}")
                        print(f"  Total tokens: {stats['total_tokens']}")
                        print(f"  Avg tokens/message: {stats['avg_tokens_per_message']:.1f}")
                    else:
                        print("\n⚠ Chat history is disabled")
                
                else:
                    print(f"\n⚠ Unknown command: {user_input}")
                    print("Type /help for available commands")
                
                continue
            
            # Process question
            question = user_input
            
            # Add to chat history
            if chat:
                chat.add_message("user", question)
            
            # Get answer
            print("\n🤖 Assistant: ", end='', flush=True)
            
            answer_parts = []
            for token in rag.query(question, stream=True):
                print(token, end='', flush=True)
                answer_parts.append(token)
            
            print()  # New line after streaming
            
            # Add to chat history
            if chat:
                answer = "".join(answer_parts)
                chat.add_message("assistant", answer)
        
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Type /exit to quit.")
        
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
