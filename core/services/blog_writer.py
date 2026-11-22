
import json

from django.db import transaction
from django.db.models import Q

from core.models import Product, BlogPost
from .groq_ai import groq_chat_json, GroqAIError


VALID_BLOG_CATEGORIES = {
    "energy_storage",
    "solar",
    "batteries",
    "commercial",
    "guides",
    "news",
}


def get_catalogue_context(topic=""):
    """
    Return a small, relevant selection of verified YUNQIDA products.

    The catalogue is deliberately limited to reduce Groq request size.
    """

    topic_words = [
        word.strip(".,!?()[]{}:;\"'")
        for word in str(topic).lower().split()
        if len(word.strip(".,!?()[]{}:;\"'")) >= 4
    ]

    ignored_words = {
        "that", "this", "with", "from", "your", "their",
        "about", "what", "when", "where", "which", "will",
        "should", "could", "would", "into", "using",
        "write", "article", "guide", "explain", "create",
        "kenya", "kenyan", "please", "make", "need",
        "want", "complete", "informative", "write",
    }

    topic_words = [
        word for word in topic_words
        if word not in ignored_words
    ][:6]

    products = Product.objects.none()

    if topic_words:
        query = Q()

        for word in topic_words:
            query |= (
                Q(name__icontains=word)
                | Q(tagline__icontains=word)
                | Q(description__icontains=word)
                | Q(manufacturer_model__icontains=word)
            )

        products = Product.objects.filter(query).order_by("name")[:4]

    catalogue = []

    for product in products:
        catalogue.append({
            "name": product.name,
            "category": product.get_category_display(),
            "model": product.manufacturer_model or "",
            "description": (product.description or "")[:250],
            "capacity": product.capacity or "",
            "power": product.power or "",
            "warranty": product.warranty or "",
            "technical_specifications": (
                product.technical_specifications or []
            ),
        })

    return json.dumps(
        catalogue,
        ensure_ascii=False,
        default=str,
    )


def generate_blog_article(topic):
    """
    Generate a complete YUNQIDA blog article and SEO assessment.

    The user supplies one prompt only.
    The AI determines the title, category, structure and SEO details.

    This function does not save or publish the article.
    """

    topic = str(topic or "").strip()

    if not topic:
        raise GroqAIError("Please enter an article prompt.")

    if len(topic) > 2000:
        raise GroqAIError(
            "Your prompt is too long. Please keep it under 2,000 characters."
        )

    catalogue = get_catalogue_context(topic)

    system_prompt = """
You are the senior technical content writer and SEO strategist
for YUNQIDA Kenya.

YUNQIDA's website focuses on energy storage, lithium batteries,
solar systems, inverters and commercial energy solutions.

Your job is to turn a simple user prompt into a complete,
high-quality, accurate and useful blog article.

IMPORTANT FACTUAL RULES:

1. Treat the supplied YUNQIDA product catalogue as the only
   authoritative source for YUNQIDA-specific product facts.

2. Never invent product models, specifications, capacities,
   inverter ratings, prices, warranties, certifications,
   stock availability or company claims.

3. If a product detail is not supplied, do not claim it.

4. You may explain general energy concepts using established
   technical knowledge. Distinguish general technical guidance
   from verified YUNQIDA product information.

5. Do not fabricate customer projects, testimonials,
   statistics, regulations or references.

6. Write naturally for Kenyan readers and businesses.

7. Avoid keyword stuffing, exaggerated marketing claims,
   repetitive wording and generic AI-style writing.

8. Do not turn every article into a sales advertisement.
   Make the content useful to readers who are researching.

ARTICLE STRUCTURE:

- Create a compelling and accurate title.
- Write an engaging introduction.
- Identify the reader's problem or information need.
- Organise the article into meaningful thematic sections.
- Use Markdown H2 headings for major sections.
- Use Markdown H3 headings for relevant subsections.
- Write informative, readable paragraphs.
- Use practical examples relevant to Kenya where appropriate.
- Include comparison tables when they genuinely improve
  understanding.
- Use bullet lists for features and considerations.
- Use numbered lists for processes and instructions.
- Use bold formatting selectively for important terms.
- Include practical guidance and actionable recommendations.
- Finish with a meaningful conclusion.

ARTICLE FORMATTING:

The article content must be written in Markdown.

Use headings, subheadings, paragraphs, lists and tables
where appropriate.

Do not return the entire article as one plain paragraph.

Do not put the article inside Markdown code fences.

Do not force a table into every article.

Never invent technical values to fill a table.

SEO REQUIREMENTS:

Generate:

- A search-friendly SEO title.
- A natural meta description.
- One primary focus keyword.
- Relevant secondary keywords.
- A useful SEO assessment.

The SEO assessment should discuss:

- Search intent.
- Keyword usage.
- Readability.
- Content structure.
- Strengths.
- Improvements.
- Relevant internal linking opportunities.

Do not claim guaranteed Google rankings.
Do not pretend to have measured actual Google search performance.
Do not invent an SEO score based on Google data.

CATEGORY:

Choose exactly one category:

energy_storage
solar
batteries
commercial
guides
news

Choose the category that best matches the actual article.

OUTPUT:

Return ONLY valid JSON.

Use exactly this structure:

{
    "title": "Article title",
    "category": "guides",
    "excerpt": "Short article summary",
    "content": "Complete article in Markdown",
    "seo_title": "SEO title",
    "meta_description": "Meta description",
    "focus_keyword": "Primary keyword",
    "secondary_keywords": [
        "keyword one",
        "keyword two"
    ],
    "seo_analysis": {
        "search_intent": "Description of search intent",
        "keyword_analysis": "Keyword analysis",
        "readability": "Readability assessment",
        "content_structure": "Structure assessment",
        "strengths": [
            "Strength one",
            "Strength two"
        ],
        "improvements": [
            "Improvement one",
            "Improvement two"
        ],
        "internal_link_suggestions": [
            "Relevant internal link suggestion"
        ]
    }
}

Do not include Markdown code fences around the JSON.
Do not include explanations outside the JSON.
"""

    user_prompt = f"""
USER'S BLOG WRITING PROMPT:

{topic}

VERIFIED YUNQIDA PRODUCT CATALOGUE:

{catalogue}

Use your editorial judgement to:

1. Understand the user's requested subject.
2. Identify the intended audience and search intent.
3. Select the most appropriate blog category.
4. Create a suitable article title.
5. Write a complete, detailed and well-structured article.
6. Generate SEO metadata and a useful SEO assessment.

Remember:
- Do not invent YUNQIDA-specific product facts.
- Use Markdown formatting throughout the article.
- Return the complete JSON structure requested.
"""

    result = groq_chat_json(
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        max_completion_tokens=5000,
    )

    if not isinstance(result, dict):
        raise GroqAIError(
            "The AI returned an invalid article structure."
        )

    title = str(result.get("title") or "").strip()
    category = str(result.get("category") or "guides").strip()
    excerpt = str(result.get("excerpt") or "").strip()
    content = str(result.get("content") or "").strip()

    seo_title = str(result.get("seo_title") or "").strip()
    meta_description = str(
        result.get("meta_description") or ""
    ).strip()

    focus_keyword = str(
        result.get("focus_keyword") or ""
    ).strip()

    secondary_keywords = result.get("secondary_keywords", [])
    seo_analysis = result.get("seo_analysis", {})

    if not title or not content:
        raise GroqAIError(
            "The AI did not return a complete article. Please try again."
        )

    if category not in VALID_BLOG_CATEGORIES:
        category = "guides"

    if not isinstance(secondary_keywords, list):
        secondary_keywords = []

    if not isinstance(seo_analysis, dict):
        seo_analysis = {}

    secondary_keywords = [
        str(keyword).strip()
        for keyword in secondary_keywords
        if isinstance(keyword, str) and keyword.strip()
    ][:15]

    return {
        "title": title[:220],
        "category": category,
        "excerpt": excerpt[:350],
        "content": content,
        "seo_title": seo_title[:70],
        "meta_description": meta_description[:170],
        "focus_keyword": focus_keyword[:120],
        "secondary_keywords": secondary_keywords,
        "seo_analysis": seo_analysis,
        "original_prompt": topic,
    }


@transaction.atomic
def save_generated_blog_article(article_data):
    """
    Save an AI-generated article as a draft.

    The article is not published automatically.
    An administrator must review and publish it.
    """

    if not isinstance(article_data, dict):
        raise GroqAIError("Invalid article data.")

    required_fields = [
        "title",
        "category",
        "excerpt",
        "content",
    ]

    for field in required_fields:
        if not article_data.get(field):
            raise GroqAIError(
                f"The generated article is missing: {field}."
            )

    category = article_data.get("category", "guides")

    if category not in VALID_BLOG_CATEGORIES:
        category = "guides"

    post = BlogPost(
        title=article_data["title"],
        category=category,
        excerpt=article_data.get("excerpt", ""),
        content=article_data["content"],
        original_prompt=article_data.get("original_prompt", ""),
        ai_generated=True,
        seo_title=article_data.get("seo_title", ""),
        meta_description=article_data.get("meta_description", ""),
        focus_keyword=article_data.get("focus_keyword", ""),
        secondary_keywords=article_data.get("secondary_keywords", []),
        seo_analysis=article_data.get("seo_analysis", {}),
        status="draft",
    )

    post.save()

    return post
