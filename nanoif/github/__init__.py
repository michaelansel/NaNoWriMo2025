"""GitHub integration for the Actions workflows: REST client, sticky comments, check runs.

Nothing here talks to an LLM. The workflows run ``nanoif ai review`` to produce
``ai-review.json`` and then ``nanoif github report`` to publish it.
"""
