"""
Custom Content Extractor Example

This example demonstrates how to create and register custom content extractors
for the web_mcp server. Custom extractors allow you to extract specific structured
data from web pages, such as recipes, product information, or any domain-specific content.

Usage:
    # Test the extractor directly
    uv run python examples/custom_extractor.py

    # Import in your own code
    from examples.custom_extractor import RecipeExtractor, ProductExtractor
"""

import asyncio
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from web_mcp.extractors.base import ContentExtractor, ExtractedContent

# =============================================================================
# STEP 1: Define Custom Data Structures (Optional)
# =============================================================================


@dataclass
class RecipeData:
    """Structured recipe data extracted from a web page."""

    name: str | None = None
    ingredients: list[str] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)
    prep_time: str | None = None
    cook_time: str | None = None
    servings: str | None = None
    cuisine: str | None = None


@dataclass
class ProductData:
    """Structured product data extracted from an e-commerce page."""

    name: str | None = None
    price: float | None = None
    currency: str = "USD"
    original_price: float | None = None
    availability: str | None = None
    rating: float | None = None
    review_count: int | None = None
    sku: str | None = None


# =============================================================================
# STEP 2: Create Custom Extractor Classes
# =============================================================================


class RecipeExtractor(ContentExtractor):
    """
    Extract recipe data from cooking websites.

    This extractor targets common recipe page structures including:
    - Schema.org Recipe JSON-LD markup
    - Common recipe HTML patterns (ingredients lists, instruction steps)
    - Recipe metadata (times, servings, cuisine)

    Example usage:
        extractor = RecipeExtractor()
        result = await extractor.extract(html, "https://example.com/recipe")
        recipe = result.metadata.get("recipe")
    """

    name = "recipe"

    def __init__(
        self,
        ingredient_selector: str = ".ingredient, .ingredients li, [itemprop='recipeIngredient']",
        instruction_selector: str = ".instruction, .instructions li, [itemprop='recipeInstructions'] li",
        title_selector: str = "h1, .recipe-title, [itemprop='name']",
    ):
        """Initialize the recipe extractor with custom selectors.

        Args:
            ingredient_selector: CSS selector for ingredient items
            instruction_selector: CSS selector for instruction steps
            title_selector: CSS selector for recipe title
        """
        self.ingredient_selector = ingredient_selector
        self.instruction_selector = instruction_selector
        self.title_selector = title_selector

    async def extract(self, html: str, url: str) -> ExtractedContent:
        """Extract recipe content from HTML.

        Args:
            html: Raw HTML content from a recipe page
            url: Source URL (used for metadata and error messages)

        Returns:
            ExtractedContent with recipe data in metadata["recipe"]
        """
        soup = BeautifulSoup(html, "html.parser")
        recipe = RecipeData()

        # Extract title
        title_elem = soup.select_one(self.title_selector)
        if title_elem:
            recipe.name = title_elem.get_text(strip=True)

        # Extract ingredients
        ingredient_elems = soup.select(self.ingredient_selector)
        recipe.ingredients = [
            self._clean_ingredient(elem.get_text(strip=True))
            for elem in ingredient_elems
            if elem.get_text(strip=True)
        ]

        # Extract instructions
        instruction_elems = soup.select(self.instruction_selector)
        recipe.instructions = [
            self._clean_instruction(elem.get_text(strip=True))
            for elem in instruction_elems
            if elem.get_text(strip=True)
        ]

        # Extract timing information
        recipe.prep_time = self._extract_time(soup, "prep")
        recipe.cook_time = self._extract_time(soup, "cook")

        # Extract servings
        servings_elem = soup.select_one(".servings, .yield, [itemprop='recipeYield']")
        if servings_elem:
            recipe.servings = servings_elem.get_text(strip=True)

        # Extract cuisine type
        cuisine_elem = soup.select_one(".cuisine, [itemprop='recipeCuisine']")
        if cuisine_elem:
            recipe.cuisine = cuisine_elem.get_text(strip=True)

        # Try to extract from JSON-LD schema.org markup (more reliable)
        recipe = self._extract_from_json_ld(soup, recipe)

        # Build text content
        text_parts = []
        if recipe.name:
            text_parts.append(f"Recipe: {recipe.name}")
        if recipe.ingredients:
            text_parts.append("\nIngredients:")
            text_parts.extend(f"- {ing}" for ing in recipe.ingredients)
        if recipe.instructions:
            text_parts.append("\nInstructions:")
            text_parts.extend(f"{i + 1}. {step}" for i, step in enumerate(recipe.instructions))

        text = "\n".join(text_parts)

        return ExtractedContent(
            title=recipe.name,
            author=None,
            date=None,
            language=None,
            text=text,
            url=url,
            metadata={
                "url": url,
                "extractor": self.name,
                "recipe": {
                    "name": recipe.name,
                    "ingredients": recipe.ingredients,
                    "instructions": recipe.instructions,
                    "prep_time": recipe.prep_time,
                    "cook_time": recipe.cook_time,
                    "servings": recipe.servings,
                    "cuisine": recipe.cuisine,
                },
            },
        )

    def _clean_ingredient(self, text: str) -> str:
        """Clean and normalize ingredient text."""
        # Remove extra whitespace
        text = " ".join(text.split())
        # Remove common prefixes
        text = re.sub(r"^\s*[-•*]\s*", "", text)
        return text

    def _clean_instruction(self, text: str) -> str:
        """Clean and normalize instruction text."""
        text = " ".join(text.split())
        # Remove step numbers
        text = re.sub(r"^\s*(?:Step\s*)?\d+[\.\)]\s*", "", text, flags=re.IGNORECASE)
        return text

    def _extract_time(self, soup: BeautifulSoup, time_type: str) -> str | None:
        """Extract prep or cook time from various formats."""
        selectors = [
            f".{time_type}-time",
            f"[itemprop='{time_type}Time']",
            f"[class*='{time_type}']",
        ]
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                # Try to extract datetime attribute
                datetime_attr = elem.get("datetime")
                if datetime_attr:
                    return datetime_attr
                return text
        return None

    def _extract_from_json_ld(self, soup: BeautifulSoup, recipe: RecipeData) -> RecipeData:
        """Extract recipe data from Schema.org JSON-LD markup."""
        import json

        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                data = json.loads(script.string or "{}")
                # Handle @graph arrays
                if "@graph" in data:
                    for item in data["@graph"]:
                        if item.get("@type") == "Recipe":
                            data = item
                            break
                # Check if this is a Recipe schema
                if data.get("@type") != "Recipe":
                    continue

                # Extract fields from JSON-LD
                if not recipe.name:
                    recipe.name = data.get("name")
                if not recipe.ingredients:
                    recipe.ingredients = data.get("recipeIngredient", [])
                if not recipe.instructions:
                    instructions = data.get("recipeInstructions", [])
                    if isinstance(instructions, list):
                        recipe.instructions = [
                            item.get("text", str(item)) if isinstance(item, dict) else str(item)
                            for item in instructions
                        ]
                if not recipe.prep_time:
                    recipe.prep_time = data.get("prepTime")
                if not recipe.cook_time:
                    recipe.cook_time = data.get("cookTime")
                if not recipe.servings:
                    recipe.servings = str(data.get("recipeYield", ""))
                if not recipe.cuisine:
                    recipe.cuisine = data.get("recipeCuisine")

            except (json.JSONDecodeError, TypeError):
                continue

        return recipe


class ProductExtractor(ContentExtractor):
    """
    Extract product data from e-commerce websites.

    This extractor targets common e-commerce page structures including:
    - Schema.org Product JSON-LD markup
    - Common product HTML patterns (price, availability, ratings)
    - Product metadata (SKU, variants)

    Example usage:
        extractor = ProductExtractor()
        result = await extractor.extract(html, "https://shop.example.com/product")
        product = result.metadata.get("product")
    """

    name = "product"

    # Price regex patterns for different formats
    PRICE_PATTERNS = [
        r"[\$€£¥]\s*([\d,]+\.?\d*)",  # $1,234.56
        r"([\d,]+\.?\d*)\s*(?:USD|EUR|GBP|JPY)",  # 1234.56 USD
        r"([\d,]+[.,]\d{2})",  # 1.234,56 or 1,234.56
    ]

    def __init__(
        self,
        price_selector: str = ".price, .product-price, [itemprop='price'], .current-price",
        title_selector: str = "h1, .product-title, [itemprop='name']",
        availability_selector: str = ".availability, .stock, [itemprop='availability']",
        rating_selector: str = ".rating, .stars, [itemprop='ratingValue']",
    ):
        """Initialize the product extractor with custom selectors.

        Args:
            price_selector: CSS selector for price element
            title_selector: CSS selector for product title
            availability_selector: CSS selector for availability/stock
            rating_selector: CSS selector for rating value
        """
        self.price_selector = price_selector
        self.title_selector = title_selector
        self.availability_selector = availability_selector
        self.rating_selector = rating_selector

    async def extract(self, html: str, url: str) -> ExtractedContent:
        """Extract product content from HTML.

        Args:
            html: Raw HTML content from a product page
            url: Source URL (used for metadata and error messages)

        Returns:
            ExtractedContent with product data in metadata["product"]
        """
        soup = BeautifulSoup(html, "html.parser")
        product = ProductData()

        # Extract title
        title_elem = soup.select_one(self.title_selector)
        if title_elem:
            product.name = title_elem.get_text(strip=True)

        # Extract price
        price_elem = soup.select_one(self.price_selector)
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            product.price, product.currency = self._parse_price(price_text)
            # Check for content attribute (common in microdata)
            content_price = price_elem.get("content")
            if content_price and not product.price:
                try:
                    product.price = float(content_price)
                except ValueError:
                    pass

        # Extract original price (for sale items)
        original_price_elem = soup.select_one(".original-price, .was-price, .list-price, .msrp")
        if original_price_elem:
            price_text = original_price_elem.get_text(strip=True)
            product.original_price, _ = self._parse_price(price_text)

        # Extract availability
        availability_elem = soup.select_one(self.availability_selector)
        if availability_elem:
            product.availability = availability_elem.get_text(strip=True)
            # Check for href/content attributes (schema.org)
            href = availability_elem.get("href", "")
            if "InStock" in href or "in-stock" in href.lower():
                product.availability = "In Stock"
            elif "OutOfStock" in href or "out-of-stock" in href.lower():
                product.availability = "Out of Stock"

        # Extract rating
        rating_elem = soup.select_one(self.rating_selector)
        if rating_elem:
            rating_text = rating_elem.get_text(strip=True)
            product.rating = self._parse_rating(rating_text)
            # Check for content attribute
            content_rating = rating_elem.get("content")
            if content_rating and not product.rating:
                try:
                    product.rating = float(content_rating)
                except ValueError:
                    pass

        # Extract review count
        review_elem = soup.select_one(".review-count, .num-reviews, [itemprop='reviewCount']")
        if review_elem:
            count_text = review_elem.get_text(strip=True)
            numbers = re.findall(r"\d+", count_text)
            if numbers:
                product.review_count = int(numbers[0])

        # Extract SKU
        sku_elem = soup.select_one(".sku, [itemprop='sku'], [data-sku]")
        if sku_elem:
            product.sku = sku_elem.get("data-sku") or sku_elem.get_text(strip=True)

        # Try to extract from JSON-LD schema.org markup
        product = self._extract_from_json_ld(soup, product)

        # Build text content
        text_parts = []
        if product.name:
            text_parts.append(f"Product: {product.name}")
        if product.price is not None:
            price_str = f"{product.currency} {product.price:.2f}"
            if product.original_price:
                price_str += f" (was {product.original_price:.2f})"
            text_parts.append(f"Price: {price_str}")
        if product.availability:
            text_parts.append(f"Availability: {product.availability}")
        if product.rating is not None:
            rating_str = f"Rating: {product.rating:.1f}/5"
            if product.review_count:
                rating_str += f" ({product.review_count} reviews)"
            text_parts.append(rating_str)
        if product.sku:
            text_parts.append(f"SKU: {product.sku}")

        text = "\n".join(text_parts)

        return ExtractedContent(
            title=product.name,
            author=None,
            date=None,
            language=None,
            text=text,
            url=url,
            metadata={
                "url": url,
                "extractor": self.name,
                "product": {
                    "name": product.name,
                    "price": product.price,
                    "currency": product.currency,
                    "original_price": product.original_price,
                    "availability": product.availability,
                    "rating": product.rating,
                    "review_count": product.review_count,
                    "sku": product.sku,
                },
            },
        )

    def _parse_price(self, text: str) -> tuple[float | None, str]:
        """Parse price from text, returning (price, currency)."""
        currency = "USD"
        if "€" in text:
            currency = "EUR"
        elif "£" in text:
            currency = "GBP"
        elif "¥" in text:
            currency = "JPY"

        for pattern in self.PRICE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                price_str = match.group(1).replace(",", "")
                try:
                    return float(price_str), currency
                except ValueError:
                    continue
        return None, currency

    def _parse_rating(self, text: str) -> float | None:
        """Parse rating value from text (e.g., '4.5 out of 5' -> 4.5)."""
        # Try to find a decimal number
        match = re.search(r"(\d+\.?\d*)", text)
        if match:
            try:
                rating = float(match.group(1))
                # Normalize to 5-point scale if needed
                if rating > 5 and rating <= 100:
                    rating = rating / 20  # Convert percentage to 5-point scale
                elif rating > 5:
                    rating = None
                return rating
            except ValueError:
                pass
        return None

    def _extract_from_json_ld(self, soup: BeautifulSoup, product: ProductData) -> ProductData:
        """Extract product data from Schema.org JSON-LD markup."""
        import json

        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                data = json.loads(script.string or "{}")
                # Handle @graph arrays
                if "@graph" in data:
                    for item in data["@graph"]:
                        if item.get("@type") == "Product":
                            data = item
                            break
                # Check if this is a Product schema
                if data.get("@type") != "Product":
                    continue

                # Extract fields from JSON-LD
                if not product.name:
                    product.name = data.get("name")
                if not product.sku:
                    product.sku = data.get("sku")

                # Extract offers (price, availability)
                offers = data.get("offers", {})
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}

                if product.price is None:
                    price = offers.get("price")
                    if price:
                        try:
                            product.price = float(price)
                            product.currency = offers.get("priceCurrency", "USD")
                        except (ValueError, TypeError):
                            pass

                if not product.availability:
                    availability = offers.get("availability", "")
                    if "InStock" in availability:
                        product.availability = "In Stock"
                    elif "OutOfStock" in availability:
                        product.availability = "Out of Stock"
                    elif "PreOrder" in availability:
                        product.availability = "Pre-Order"

                # Extract aggregate rating
                rating = data.get("aggregateRating", {})
                if product.rating is None:
                    rating_value = rating.get("ratingValue")
                    if rating_value:
                        try:
                            product.rating = float(rating_value)
                        except (ValueError, TypeError):
                            pass
                if product.review_count is None:
                    count = rating.get("reviewCount") or rating.get("ratingCount")
                    if count:
                        try:
                            product.review_count = int(count)
                        except (ValueError, TypeError):
                            pass

            except (json.JSONDecodeError, TypeError):
                continue

        return product


# =============================================================================
# STEP 3: Extractor Registry (Optional - for managing multiple extractors)
# =============================================================================


class ExtractorRegistry:
    """
    Registry for managing multiple content extractors.

    This allows you to register extractors by name and retrieve them
    based on URL patterns or content types.

    Example:
        registry = ExtractorRegistry()
        registry.register(RecipeExtractor(), ["recipe", "cooking"])
        registry.register(ProductExtractor(), ["product", "shop"])

        extractor = registry.get("recipe")
        # or
        extractor = registry.get_for_url("https://cooking.example.com/recipe/123")
    """

    def __init__(self):
        self._extractors: dict[str, ContentExtractor] = {}
        self._url_patterns: dict[str, list[str]] = {}

    def register(
        self,
        extractor: ContentExtractor,
        aliases: list[str] | None = None,
        url_patterns: list[str] | None = None,
    ) -> None:
        """Register an extractor.

        Args:
            extractor: The ContentExtractor instance
            aliases: Alternative names for this extractor
            url_patterns: URL patterns (regex) that this extractor handles
        """
        name = extractor.name
        self._extractors[name] = extractor

        if aliases:
            for alias in aliases:
                self._extractors[alias] = extractor

        if url_patterns:
            self._url_patterns[name] = url_patterns

    def get(self, name: str) -> ContentExtractor | None:
        """Get an extractor by name or alias."""
        return self._extractors.get(name)

    def get_for_url(self, url: str) -> ContentExtractor | None:
        """Get the best extractor for a given URL based on patterns."""
        for name, patterns in self._url_patterns.items():
            for pattern in patterns:
                if re.search(pattern, url):
                    return self._extractors.get(name)
        return None

    def list_extractors(self) -> list[str]:
        """List all registered extractor names."""
        return list({e.name for e in self._extractors.values()})


# =============================================================================
# STEP 4: Using Extractors with the MCP Server
# =============================================================================


async def use_with_mcp_server(html: str, url: str) -> str:
    """
    Example of how to use custom extractors with the MCP server.

    The web_mcp server uses extractors in the get_page tool. You can
    modify the server to support custom extractors by:

    1. Adding your extractor to the server's extractor selection logic
    2. Passing the extractor name via the 'extractor' parameter

    Note: This requires modifying server.py to add support for custom
    extractors. The default extractors are: trafilatura, readability, custom
    """
    # Create your custom extractor
    recipe_extractor = RecipeExtractor()

    # Use it to extract content
    result = await recipe_extractor.extract(html, url)

    # Return the extracted text (or access structured data via metadata)
    recipe_data = result.metadata.get("recipe", {})
    print(f"Extracted recipe: {recipe_data.get('name')}")
    print(f"Ingredients: {len(recipe_data.get('ingredients', []))} items")

    return result.text


# =============================================================================
# STEP 5: Testing Your Custom Extractor
# =============================================================================

# Sample HTML for testing
SAMPLE_RECIPE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Grandma's Apple Pie</title>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": "Grandma's Apple Pie",
        "recipeIngredient": [
            "6 cups sliced apples",
            "3/4 cup sugar",
            "2 tbsp flour",
            "1 tsp cinnamon",
            "2 pie crusts"
        ],
        "recipeInstructions": [
            {"@type": "HowToStep", "text": "Preheat oven to 425°F"},
            {"@type": "HowToStep", "text": "Mix apples with sugar, flour, and cinnamon"},
            {"@type": "HowToStep", "text": "Place in pie crust and cover with top crust"},
            {"@type": "HowToStep", "text": "Bake for 45 minutes until golden"}
        ],
        "prepTime": "PT30M",
        "cookTime": "PT45M",
        "recipeYield": "8 servings"
    }
    </script>
</head>
<body>
    <h1 class="recipe-title">Grandma's Apple Pie</h1>
    <div class="ingredients">
        <li>6 cups sliced apples</li>
        <li>3/4 cup sugar</li>
        <li>2 tbsp flour</li>
        <li>1 tsp cinnamon</li>
        <li>2 pie crusts</li>
    </div>
    <div class="instructions">
        <li>Preheat oven to 425°F</li>
        <li>Mix apples with sugar, flour, and cinnamon</li>
        <li>Place in pie crust and cover with top crust</li>
        <li>Bake for 45 minutes until golden</li>
    </div>
</body>
</html>
"""

SAMPLE_PRODUCT_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Wireless Headphones - ShopExample</title>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Pro Wireless Headphones",
        "sku": "WH-1000XM5",
        "offers": {
            "@type": "Offer",
            "price": "299.99",
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock"
        },
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": "4.7",
            "reviewCount": "1523"
        }
    }
    </script>
</head>
<body>
    <h1 class="product-title">Pro Wireless Headphones</h1>
    <div class="price">$299.99</div>
    <div class="original-price">$349.99</div>
    <div class="availability">In Stock</div>
    <div class="rating">4.7 out of 5 stars</div>
    <span class="review-count">(1,523 reviews)</span>
</body>
</html>
"""


async def test_recipe_extractor():
    """Test the RecipeExtractor with sample HTML."""
    print("=" * 60)
    print("Testing RecipeExtractor")
    print("=" * 60)

    extractor = RecipeExtractor()
    result = await extractor.extract(SAMPLE_RECIPE_HTML, "https://example.com/recipe/apple-pie")

    print(f"\nExtracted Text:\n{result.text}")
    print("\nMetadata:")
    recipe = result.metadata.get("recipe", {})
    print(f"  Name: {recipe.get('name')}")
    print(f"  Prep Time: {recipe.get('prep_time')}")
    print(f"  Cook Time: {recipe.get('cook_time')}")
    print(f"  Servings: {recipe.get('servings')}")
    print(f"  Ingredients ({len(recipe.get('ingredients', []))}):")
    for ing in recipe.get("ingredients", [])[:3]:
        print(f"    - {ing}")
    print(f"  Instructions ({len(recipe.get('instructions', []))} steps)")


async def test_product_extractor():
    """Test the ProductExtractor with sample HTML."""
    print("\n" + "=" * 60)
    print("Testing ProductExtractor")
    print("=" * 60)

    extractor = ProductExtractor()
    result = await extractor.extract(SAMPLE_PRODUCT_HTML, "https://shop.example.com/headphones")

    print(f"\nExtracted Text:\n{result.text}")
    print("\nMetadata:")
    product = result.metadata.get("product", {})
    print(f"  Name: {product.get('name')}")
    print(f"  Price: {product.get('currency')} {product.get('price')}")
    print(f"  Original Price: {product.get('original_price')}")
    print(f"  Availability: {product.get('availability')}")
    print(f"  Rating: {product.get('rating')}/5 ({product.get('review_count')} reviews)")
    print(f"  SKU: {product.get('sku')}")


async def test_error_handling():
    """Test error handling with malformed HTML."""
    print("\n" + "=" * 60)
    print("Testing Error Handling")
    print("=" * 60)

    extractor = RecipeExtractor()

    # Test with empty HTML
    result = await extractor.extract("", "https://example.com/empty")
    print(f"\nEmpty HTML result: title={result.title}, text_length={len(result.text)}")

    # Test with malformed HTML
    result = await extractor.extract("<html><broken>", "https://example.com/broken")
    print(f"Malformed HTML result: title={result.title}, text_length={len(result.text)}")

    # Test with non-recipe content
    result = await extractor.extract(
        "<html><body><p>Just some text</p></body></html>", "https://example.com/text"
    )
    print(
        f"Non-recipe HTML result: ingredients={result.metadata.get('recipe', {}).get('ingredients')}"
    )


async def test_registry():
    """Test the ExtractorRegistry."""
    print("\n" + "=" * 60)
    print("Testing ExtractorRegistry")
    print("=" * 60)

    registry = ExtractorRegistry()

    # Register extractors with URL patterns
    registry.register(
        RecipeExtractor(), aliases=["cooking"], url_patterns=[r"recipe", r"cooking", r"food\.com"]
    )
    registry.register(
        ProductExtractor(),
        aliases=["shop", "ecommerce"],
        url_patterns=[r"shop", r"product", r"store\.com"],
    )

    print(f"\nRegistered extractors: {registry.list_extractors()}")

    # Test getting by name
    extractor = registry.get("recipe")
    print(f"Get 'recipe': {extractor.__class__.__name__ if extractor else None}")

    # Test getting by alias
    extractor = registry.get("cooking")
    print(f"Get 'cooking' (alias): {extractor.__class__.__name__ if extractor else None}")

    # Test URL matching
    test_urls = [
        "https://cooking.example.com/recipe/apple-pie",
        "https://shop.example.com/product/headphones",
        "https://example.com/blog/post",
    ]

    print("\nURL Pattern Matching:")
    for url in test_urls:
        extractor = registry.get_for_url(url)
        name = extractor.name if extractor else "None"
        print(f"  {url} -> {name}")


async def main():
    """Run all tests."""
    print("\n" + "#" * 60)
    print("# Custom Content Extractor Examples")
    print("#" * 60)

    await test_recipe_extractor()
    await test_product_extractor()
    await test_error_handling()
    await test_registry()

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
