# Technical Requirements
1. Use `Python` as the main language. Use `uv` to manage dependencies. Only if necessary, use NodeJS for glue code that talks to Gemini CLI.
2. Respect Python idioms: All Python source code should be placed under the `src` directory. The `src` directory itself should not be a Python package, and the entrypoint should be a file placed under the `src` directory.
3. Always consult and strictly adhere to the `DESIGN.md` document throughout the entire development process. Ensure architectural alignment with the design doc before making implementation decisions. If the user asks new features or changes, always update `DESIGN.md` to be consistent.
