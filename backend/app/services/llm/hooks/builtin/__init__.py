"""Builtin hooks.

Importing a module here registers its hooks as a side effect, which is why
`load_builtin_hooks()` imports them explicitly rather than this package doing it
at import time — tests need to build an empty registry without them.

Priority bands used across the builtins, so ordering stays predictable as more
are added:

    10-39   normalize   argument rewriting (must run first)
    40-69   guards      validation and refusal (sees corrected arguments)
    10-39   side_effects POST_TOOL rendering (own event, own band)
    90-100  audit       tallies and logging (must run last)
"""
