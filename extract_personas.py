#!/usr/bin/env python3
"""
Extract persona prompts from raw data (tweets, papers, talks, github)
Converts: personas_data/{name}/*.json -> personas/{name}.md
"""

import json
import os
from pathlib import Path
from anthropic import Anthropic

# Paths
PERSONAS_DATA_DIR = Path("personas_data")
PERSONAS_OUTPUT_DIR = Path("personas")
PERSONAS_OUTPUT_DIR.mkdir(exist_ok=True)

# Initialize Anthropic client
client = Anthropic()

EXTRACTION_PROMPT = """You are a Personality Analyzer for AI/Tech Experts.

Your task: Given a collection of data (tweets, papers, talks, GitHub projects) from a person, extract their authentic personality,
thinking style, priorities, and communication patterns. This will be used to create an agent system prompt
that thinks and communicates like them.

ANALYZE THE DATA:

1. CORE THINKING PATTERNS
   - What do they obsess over? (themes that repeat)
   - What assumptions do they challenge?
   - How do they approach problems? (first-principles? iterative? data-driven?)
   - What do they dismiss as "hype" or "solved"?

2. VALUES & PRIORITIES
   - What outcomes matter to them? (speed? quality? efficiency? safety?)
   - What trade-offs do they make? (fast vs perfect? simple vs complete?)
   - What do they criticize in others?
   - What gets them excited/frustrated?

3. COMMUNICATION STYLE
   - Tone: blunt or diplomatic? Educational or prescriptive?
   - Use concrete examples or abstract principles?
   - Ask questions or state conclusions?
   - Humor? Self-deprecation? Confidence level?

4. EXPERTISE DOMAINS
   - What are they actually qualified to speak on?
   - What do they reference in their work?
   - Blind spots or areas they avoid?

5. DEBATE STYLE
   - How do they respond to disagreement?
   - Do they cite evidence or rely on intuition?
   - How do they frame counter-arguments?

OUTPUT FORMAT (as system prompt for an agent):

---
NAME: [Person]
TAGLINE: [One-liner of their brand]

CORE BELIEFS:
- [Belief 1]
- [Belief 2]
- [Belief 3]

THINKING STYLE:
"[Describe how they approach problems in 2-3 sentences. Include actual patterns/examples from data]"

PRIORITIES:
- [Most important 1]
- [Most important 2]

WHAT THEY QUESTION:
- "Why do we assume X?"
- "Is constraint Y actually real?"

COMMUNICATION STYLE:
- Tone: [blunt/diplomatic/educational/provocative]
- Structure: [how they organize thoughts]
- Evidence: [data-driven / intuition-based / example-heavy]

DEBATE PATTERNS:
- When disagreed with: [typical response]
- On evidence: [how they use data]

EXAMPLE PHRASES/PATTERNS:
(Actual quotes or paraphrases from their work)
- "[Example 1]"
- "[Example 2]"

BLIND SPOTS:
- [Area they seem less informed on]

RED FLAGS:
- Avoid sounding like: [don't make them sound like X]
- Authentic: [specific instruction to sound real]

---

CRITICAL:
- Use ONLY what appears in the data (don't assume)
- Be specific — avoid generic descriptors
- Quote or paraphrase actual phrases when possible
- Your output will be used as a system prompt, so make it authentic
- Focus on making the agent think and respond like this person would
"""


def load_persona_data(person_name: str) -> dict:
    """Load raw data for a person from personas_data folder"""
    person_dir = PERSONAS_DATA_DIR / person_name

    if not person_dir.exists():
        print(f"❌ Directory not found: {person_dir}")
        return {}

    data = {"name": person_name}

    # Load tweets/text data
    files_to_load = {
        "tweets": "tweets.json",
        "papers": "papers.json",
        "github_projects": "github_projects.json",
        "talks": "talks.txt",
        "blog_posts": "blog_posts.md",
    }

    for key, filename in files_to_load.items():
        filepath = person_dir / filename
        if filepath.exists():
            try:
                if filename.endswith(".json"):
                    with open(filepath) as f:
                        data[key] = json.load(f)
                else:
                    with open(filepath) as f:
                        data[key] = f.read()
                print(f"  ✓ Loaded {filename}")
            except Exception as e:
                print(f"  ⚠ Error loading {filename}: {e}")
                data[key] = None
        else:
            data[key] = None

    return data


def extract_persona(person_name: str, person_data: dict) -> str:
    """Extract persona using Claude"""

    print(f"\n🔄 Extracting persona for {person_name}...")

    # Format the data for the prompt
    data_summary = f"Data for {person_name}:\n\n"

    if person_data.get("tweets"):
        tweets = person_data["tweets"]
        if isinstance(tweets, dict):
            tweet_count = len(tweets.get("tweets", []))
            data_summary += f"📱 Tweets: {tweet_count} tweets\n"
        else:
            data_summary += f"📱 Tweets:\n{str(tweets)[:500]}...\n"

    if person_data.get("papers"):
        papers = person_data["papers"]
        if isinstance(papers, dict):
            paper_count = len(papers.get("papers", []))
            data_summary += f"📄 Papers: {paper_count} papers\n"
        else:
            data_summary += f"📄 Papers:\n{str(papers)[:500]}...\n"

    if person_data.get("github_projects"):
        projects = person_data["github_projects"]
        if isinstance(projects, dict):
            project_count = len(projects.get("projects", []))
            data_summary += f"💻 GitHub: {project_count} projects\n"
        else:
            data_summary += f"💻 GitHub:\n{str(projects)[:500]}...\n"

    if person_data.get("talks"):
        talks = person_data["talks"]
        if talks:
            data_summary += f"🎤 Talks: {len(talks)} characters of transcripts\n"

    if person_data.get("blog_posts"):
        blog = person_data["blog_posts"]
        if blog:
            data_summary += f"✍️ Blog: {len(blog)} characters of writing\n"

    # Create full data string for Claude
    full_data = data_summary + "\n\nFULL DATA:\n"

    if person_data.get("tweets"):
        full_data += f"\n## TWEETS\n{json.dumps(person_data['tweets'], indent=2)[:2000]}...\n"

    if person_data.get("papers"):
        full_data += f"\n## PAPERS\n{json.dumps(person_data['papers'], indent=2)[:1500]}...\n"

    if person_data.get("github_projects"):
        full_data += f"\n## GITHUB\n{json.dumps(person_data['github_projects'], indent=2)[:1500]}...\n"

    if person_data.get("talks"):
        talks_text = person_data["talks"]
        if isinstance(talks_text, str):
            full_data += f"\n## TALKS\n{talks_text[:2000]}...\n"

    if person_data.get("blog_posts"):
        blog_text = person_data["blog_posts"]
        if isinstance(blog_text, str):
            full_data += f"\n## BLOG\n{blog_text[:1000]}...\n"

    # Call Claude
    response = client.messages.create(
        model="claude-opus-4-1-20250805",
        max_tokens=2000,
        system=EXTRACTION_PROMPT,
        messages=[
            {
                "role": "user",
                "content": full_data
            }
        ]
    )

    persona_text = response.content[0].text
    print(f"✅ Extracted persona for {person_name}")

    return persona_text


def save_persona(person_name: str, persona_text: str) -> Path:
    """Save extracted persona to file"""
    # Sanitize filename
    safe_name = person_name.replace(" ", "_").lower()
    output_path = PERSONAS_OUTPUT_DIR / f"{safe_name}.md"

    with open(output_path, "w") as f:
        f.write(f"# {person_name}\n\n")
        f.write(persona_text)

    print(f"💾 Saved to: {output_path}")
    return output_path


def main():
    """Extract all personas"""

    print("=" * 70)
    print("PERSONA EXTRACTION PIPELINE")
    print("=" * 70)

    # Get all person folders
    person_folders = sorted([d.name for d in PERSONAS_DATA_DIR.iterdir() if d.is_dir()])

    print(f"\n📂 Found {len(person_folders)} people in personas_data/\n")

    results = {
        "success": [],
        "failed": []
    }

    for i, person_name in enumerate(person_folders, 1):
        print(f"\n[{i}/{len(person_folders)}] {person_name}")
        print("-" * 70)

        try:
            # Load data
            person_data = load_persona_data(person_name)

            if not person_data or all(v is None for k, v in person_data.items() if k != "name"):
                print(f"❌ No data found for {person_name}")
                results["failed"].append(person_name)
                continue

            # Extract persona
            persona_text = extract_persona(person_name, person_data)

            # Save persona
            output_path = save_persona(person_name, persona_text)
            results["success"].append((person_name, output_path))

        except Exception as e:
            print(f"❌ Error processing {person_name}: {e}")
            results["failed"].append(person_name)

    # Summary
    print("\n" + "=" * 70)
    print("EXTRACTION SUMMARY")
    print("=" * 70)
    print(f"✅ Success: {len(results['success'])}")
    print(f"❌ Failed: {len(results['failed'])}")

    if results["success"]:
        print(f"\n📁 Personas saved to: {PERSONAS_OUTPUT_DIR}/")
        for person, path in results["success"]:
            print(f"  ✓ {path.name}")

    if results["failed"]:
        print(f"\n⚠️  Failed personas:")
        for person in results["failed"]:
            print(f"  ✗ {person}")

    # Create index
    create_personas_index(results["success"])


def create_personas_index(successful_personas: list):
    """Create personas_index.json"""
    index = {
        "personas": [
            {
                "name": person,
                "file": f"{person.replace(' ', '_').lower()}.md",
                "path": str(path)
            }
            for person, path in successful_personas
        ]
    }

    index_path = PERSONAS_OUTPUT_DIR / "personas_index.json"
    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)

    print(f"\n📑 Created index: {index_path}")


if __name__ == "__main__":
    main()
