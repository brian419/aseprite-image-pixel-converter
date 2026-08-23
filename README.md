# Aseprite Image Pixel Converter

A local utility for converting large reference images into smaller, palette-limited pixel-art starting points for editing and cleanup in Aseprite.

The initial target workflow is:

```text
large PNG
    ↓
resize to a small canvas
    ↓
reduce color palette
    ↓
preserve / clean transparency
    ↓
create a pixel-oriented PNG
    ↓
manual refinement in Aseprite
This project is intended to create useful starting images, not automatically replace manual pixel-art editing.
