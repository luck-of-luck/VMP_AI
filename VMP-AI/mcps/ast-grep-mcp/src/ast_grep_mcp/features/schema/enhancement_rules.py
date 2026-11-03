"""Enhancement rules and priorities for Schema.org entity graph analysis.

This module defines the rules used by enhance_entity_graph to determine which
properties and entities should be suggested for existing Schema.org graphs.
Rules are based on:
- Schema.org vocabulary standards
- Google Rich Results guidelines
- SEO best practices
"""

from typing import Any, Dict, List

from ast_grep_mcp.models.schema_enhancement import EnhancementPriority

# Property priorities by entity type
# Maps entity types to dictionaries of property names and their importance levels
PROPERTY_PRIORITIES: Dict[str, Dict[str, EnhancementPriority]] = {
    "Organization": {
        "aggregateRating": EnhancementPriority.CRITICAL,
        "review": EnhancementPriority.CRITICAL,
        "contactPoint": EnhancementPriority.HIGH,
        "hasOfferCatalog": EnhancementPriority.MEDIUM,
        "sameAs": EnhancementPriority.MEDIUM,
        "address": EnhancementPriority.HIGH,
        "telephone": EnhancementPriority.HIGH,
    },
    "Service": {
        "offers": EnhancementPriority.HIGH,
        "termsOfService": EnhancementPriority.MEDIUM,
        "provider": EnhancementPriority.HIGH,
        "areaServed": EnhancementPriority.MEDIUM,
        "serviceType": EnhancementPriority.MEDIUM,
    },
    "Person": {
        "image": EnhancementPriority.HIGH,
        "description": EnhancementPriority.MEDIUM,
        "jobTitle": EnhancementPriority.MEDIUM,
        "worksFor": EnhancementPriority.HIGH,
        "sameAs": EnhancementPriority.MEDIUM,
    },
    "BlogPosting": {
        "wordCount": EnhancementPriority.HIGH,
        "timeRequired": EnhancementPriority.HIGH,
        "dateModified": EnhancementPriority.MEDIUM,
        "author": EnhancementPriority.HIGH,
        "image": EnhancementPriority.HIGH,
        "articleBody": EnhancementPriority.MEDIUM,
    },
    "HowTo": {
        "totalTime": EnhancementPriority.HIGH,
        "prepTime": EnhancementPriority.MEDIUM,
        "performTime": EnhancementPriority.MEDIUM,
        "step": EnhancementPriority.CRITICAL,
        "image": EnhancementPriority.HIGH,
        "supply": EnhancementPriority.MEDIUM,
        "tool": EnhancementPriority.MEDIUM,
    },
    "MedicalWebPage": {
        "medicalAudience": EnhancementPriority.HIGH,
        "reviewedBy": EnhancementPriority.MEDIUM,
        "lastReviewed": EnhancementPriority.MEDIUM,
        "specialty": EnhancementPriority.MEDIUM,
    },
    "Product": {
        "aggregateRating": EnhancementPriority.CRITICAL,
        "review": EnhancementPriority.CRITICAL,
        "offers": EnhancementPriority.CRITICAL,
        "brand": EnhancementPriority.HIGH,
        "image": EnhancementPriority.HIGH,
        "description": EnhancementPriority.HIGH,
    },
    "Recipe": {
        "recipeIngredient": EnhancementPriority.CRITICAL,
        "recipeInstructions": EnhancementPriority.CRITICAL,
        "totalTime": EnhancementPriority.HIGH,
        "recipeYield": EnhancementPriority.HIGH,
        "nutrition": EnhancementPriority.MEDIUM,
        "image": EnhancementPriority.HIGH,
    },
    "WebSite": {
        "potentialAction": EnhancementPriority.HIGH,
        "publisher": EnhancementPriority.MEDIUM,
    },
}


# Google Rich Results mapping
# Maps properties and entity types to the Google Rich Results they enable
RICH_RESULTS_MAP: Dict[str, List[str]] = {
    # Property-based rich results
    "aggregateRating": ["Organization reviews", "Product reviews", "Local business reviews"],
    "review": ["Review snippets", "Critic reviews"],
    "offers": ["Product pricing", "Service pricing", "Event tickets"],
    "recipeIngredient": ["Recipe rich results"],
    "recipeInstructions": ["Recipe rich results"],
    "step": ["How-to rich results"],
    "potentialAction": ["Sitelinks searchbox"],
    # Entity-based rich results
    "FAQPage": ["FAQ rich results"],
    "BreadcrumbList": ["Breadcrumb navigation"],
    "HowTo": ["How-to rich results"],
    "Recipe": ["Recipe rich results"],
    "Product": ["Product rich results"],
    "Event": ["Event rich results"],
    "VideoObject": ["Video rich results"],
    "Article": ["Article rich results"],
    "NewsArticle": ["News article rich results"],
    "JobPosting": ["Job posting rich results"],
}


# Entity suggestion rules
# Rules use a simple query language for pattern matching
ENTITY_SUGGESTIONS: Dict[str, Dict[str, Any]] = {
    "has:Organization AND NOT has:FAQPage": {
        "suggest": "FAQPage",
        "priority": EnhancementPriority.HIGH,
        "reason": "FAQ pages enable FAQ Rich Results and improve user engagement",
        "google_rich_result": "FAQ rich results",
    },
    "has:Organization AND NOT has:WebSite": {
        "suggest": "WebSite",
        "priority": EnhancementPriority.HIGH,
        "reason": "WebSite entity with SearchAction enables sitelinks searchbox in Google",
        "google_rich_result": "Sitelinks searchbox",
    },
    "count:WebPage>1 AND NOT has:BreadcrumbList": {
        "suggest": "BreadcrumbList",
        "priority": EnhancementPriority.MEDIUM,
        "reason": "Breadcrumbs improve navigation hierarchy and appear in search results",
        "google_rich_result": "Breadcrumb navigation",
    },
    "has:Service AND NOT has:Review": {
        "suggest": "Review",
        "priority": EnhancementPriority.CRITICAL,
        "reason": "Reviews enable rich snippets and build trust with potential customers",
        "google_rich_result": "Review snippets",
    },
    "has:BlogPosting AND NOT has:BreadcrumbList": {
        "suggest": "BreadcrumbList",
        "priority": EnhancementPriority.MEDIUM,
        "reason": "Breadcrumbs help users navigate blog structure",
        "google_rich_result": "Breadcrumb navigation",
    },
    "has:Product AND NOT has:Review": {
        "suggest": "Review",
        "priority": EnhancementPriority.CRITICAL,
        "reason": "Product reviews are critical for e-commerce rich results",
        "google_rich_result": "Product reviews",
    },
}


# Example values for common Schema.org properties
PROPERTY_EXAMPLES: Dict[str, Any] = {
    "aggregateRating": {
        "@type": "AggregateRating",
        "ratingValue": "4.5",
        "reviewCount": "250",
        "bestRating": "5",
        "worstRating": "1",
    },
    "review": {
        "@type": "Review",
        "reviewRating": {"@type": "Rating", "ratingValue": "5", "bestRating": "5"},
        "author": {"@type": "Person", "name": "Reviewer Name"},
        "reviewBody": "Example review text...",
    },
    "contactPoint": {
        "@type": "ContactPoint",
        "telephone": "+1-555-555-5555",
        "contactType": "customer service",
        "availableLanguage": ["English", "Spanish"],
        "hoursAvailable": {
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "opens": "09:00",
            "closes": "17:00",
        },
    },
    "offers": {
        "@type": "Offer",
        "price": "0",
        "priceCurrency": "USD",
        "availability": "https://schema.org/InStock",
    },
    "image": {
        "@type": "ImageObject",
        "url": "https://example.com/image.jpg",
        "width": "800",
        "height": "600",
    },
    "potentialAction": {
        "@type": "SearchAction",
        "target": {
            "@type": "EntryPoint",
            "urlTemplate": "https://example.com/search?q={search_term_string}",
        },
        "query-input": "required name=search_term_string",
    },
}


def get_property_priority(entity_type: str, property_name: str) -> EnhancementPriority:
    """Get the priority level for a property on a given entity type.

    Args:
        entity_type: The Schema.org entity type (e.g., "Organization", "Person")
        property_name: The property name (e.g., "aggregateRating", "image")

    Returns:
        EnhancementPriority level (defaults to LOW if not found in rules)
    """
    if entity_type in PROPERTY_PRIORITIES:
        entity_props = PROPERTY_PRIORITIES[entity_type]
        if property_name in entity_props:
            return entity_props[property_name]
    return EnhancementPriority.LOW


def get_rich_results_for_property(property_name: str) -> List[str]:
    """Get the list of Google Rich Results enabled by a specific property.

    Args:
        property_name: The property name (e.g., "aggregateRating", "review")

    Returns:
        List of Google Rich Result types enabled by this property
    """
    return RICH_RESULTS_MAP.get(property_name, [])


def get_rich_results_for_entity(entity_type: str) -> List[str]:
    """Get the list of Google Rich Results enabled by a specific entity type.

    Args:
        entity_type: The Schema.org entity type (e.g., "FAQPage", "HowTo")

    Returns:
        List of Google Rich Result types enabled by this entity
    """
    return RICH_RESULTS_MAP.get(entity_type, [])


def get_all_properties_for_entity(entity_type: str) -> Dict[str, EnhancementPriority]:
    """Get all enhancement properties defined for an entity type.

    Args:
        entity_type: The Schema.org entity type (e.g., "Organization", "Person")

    Returns:
        Dictionary mapping property names to their priority levels
    """
    return PROPERTY_PRIORITIES.get(entity_type, {})


def get_property_example(property_name: str) -> Any:
    """Get an example value for a property.

    Args:
        property_name: The property name

    Returns:
        Example value structure or None if not defined
    """
    return PROPERTY_EXAMPLES.get(property_name)


def get_entity_suggestions() -> Dict[str, Dict[str, Any]]:
    """Get all entity suggestion rules.

    Returns:
        Dictionary of suggestion rules with pattern matching queries
    """
    return ENTITY_SUGGESTIONS.copy()
