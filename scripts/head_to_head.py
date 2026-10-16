"""Compare two saved prediction sets without making inference calls.

Historical head-to-head posted directly to Modal and bypassed GemmaExtractor.
That historical route explains why the Gemini multiplication bug did not affect it.
"""

from scripts.compare import main

if __name__ == "__main__":
    main()
