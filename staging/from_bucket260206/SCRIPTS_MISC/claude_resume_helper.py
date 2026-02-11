#!/usr/bin/env python3
"""
Claude Resume Helper - ให้ Claude session ใหม่เรียกใช้เพื่อได้บริบท
"""
from claude_memory_manager import ClaudeMemoryManager

def get_claude_context():
    """ใช้ในช่วงเริ่มต้น Claude session ใหม่"""
    memory_manager = ClaudeMemoryManager()
    context = memory_manager.generate_context_prompt()
    
    print("📋 CLAUDE SESSION RESUME CONTEXT:")
    print("="*60)
    print(context)
    print("="*60)
    print("\n💡 Copy the context above and paste to new Claude session")
    print("🔗 This will restore Claude's memory of GG Mesh V3 progress")
    
    return context

if __name__ == "__main__":
    get_claude_context()
