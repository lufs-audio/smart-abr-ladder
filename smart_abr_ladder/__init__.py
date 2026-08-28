"""smart-abr-ladder — per-title / per-shot adaptive bitrate ladder, verified.

Probe → shot-detect → RD model → ladder select → encode → verify, where the VERIFY
stage is the product: every rendition must decode, hit its target VMAF within tolerance,
hold its bitrate band, and leave the ladder monotone with no redundant rung. A contract
violation fails (exit 5), never reports a silent green.
"""

__version__ = "0.1.0"
SCHEMA_VERSION = 1
