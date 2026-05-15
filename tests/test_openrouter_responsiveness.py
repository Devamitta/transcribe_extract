import time


from tools.openrouter import generate_content, list_models

TEST_PROMPT = "Say 'hi'"
SYSTEM_INSTRUCTION = "Be brief."


def test_models():
    """Test all free OpenRouter models for responsiveness with a 10s timeout."""
    free_models = list_models(free_only=True)
    if not free_models:
        print("No free models found or API error.")
        return

    print(f"Testing {len(free_models)} free models for responsiveness...")
    print("Goal: Identify the top 3 most responsive models for testing.\n")

    results = []
    for model in free_models:
        start_time = time.time()
        try:
            # Using a tight timeout to find truly responsive ones
            _ = generate_content(
                contents=TEST_PROMPT,
                system_instruction=SYSTEM_INSTRUCTION,
                model=model,
                timeout=10,
            )
            duration = time.time() - start_time
            print(f"  [OK] {model}: {duration:.2f}s")
            results.append((model, duration))
        except Exception:
            # Standard error logging is handled inside generate_content
            # We just need to skip it for our results list
            pass

    print("\n" + "=" * 40)
    print("Top 3 Most Responsive Models:")
    print("=" * 40)
    results.sort(key=lambda x: x[1])
    for i, (model, duration) in enumerate(results[:3], 1):
        print(f"  {i}. {model}: {duration:.2f}s")

    print(
        "\nTo update the test models, copy these into OPENROUTER_TEST_MODELS in tools/provider.py"
    )


if __name__ == "__main__":
    test_models()
