# Aseprite Image Pixel Converter

A local macOS utility for converting large reference images into crisp, low-resolution PNGs for refinement in Aseprite.

The app keeps the existing whole-image conversion workflow and adds Apple Vision smart subject lifting. In smart mode, the user can click a detected foreground subject or draw a loose lasso around it. The selected subject is lifted with the rest of the image made transparent, then passed through the same pixel conversion pipeline.
