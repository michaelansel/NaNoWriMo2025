"""
AllPaths pipeline modules.

This package contains the modular processing stages for the AllPaths pipeline:
- Stage 1: Parser (HTML → story_graph.json)
- Stage 2: Path Generator (story_graph.json → paths.json)
- Stage 3: Git Enricher (paths.json → paths_enriched.json)
- Stage 4: Categorizer (paths_enriched.json → paths_categorized.json)
- Stage 5: Output Generator (paths_categorized.json → outputs)
"""

__all__ = []
