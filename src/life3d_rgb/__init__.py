"""
life3d-rgb: 3D cellular automata with RGB inheritance and mutations.

A 3D cellular automaton simulator using 26-neighbor rules with:
- RGB color inheritance modes to prevent grayscale drift
- Mutation systems for color diversity 
- GIF animation output with death switch
- Optional Tkinter UI for interactive use
- CLI for batch processing
"""

__all__ = ["engine", "visualize", "cli", "ui", "death_switch"]
__version__ = "0.7.2"