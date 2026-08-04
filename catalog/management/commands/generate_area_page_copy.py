"""
Phase 4 item 25: AI-generated area/landing pages.

The frontend is static HTML with no CMS or templating engine behind
it (see tutoro_frontend-main/areas/*.html for the existing hand-built
locality pages) -- so "generate a page" here means generating the
marketing copy for a human to review and paste into a new static HTML
file cloned from an existing area page, not creating a live route.
That's a deliberate scope choice: publishing copy nobody reviewed
straight to a public page is a bigger risk than the time saved by
skipping a human read-through.

Usage:
    python manage.py generate_area_page_copy kukatpally --mode home
    python manage.py generate_area_page_copy madhapur --mode online --subject Mathematics
    python manage.py generate_area_page_copy warangal --mode home --output copy.json
        (works for areas not in the DB yet too -- pass --city; see
        add_arguments -- since expanding to new areas, e.g. the
        Warangal/Karimnagar SEO expansion the roadmap mentions in
        Phase 7, is exactly when this command is most useful, and
        that's before the Area row necessarily exists.)
"""

import json

from django.core.management.base import BaseCommand, CommandError

from apps.ai.client import SONNET_MODEL, AIUnavailableError, complete_json
from apps.catalog.models import Area


class Command(BaseCommand):
    help = "Generate AI marketing copy for a new area or online-tuition landing page."

    def add_arguments(self, parser):
        parser.add_argument("area_name", help="Locality name, e.g. 'Kukatpally' or 'Warangal'.")
        parser.add_argument(
            "--city", default="Hyderabad",
            help="City name -- only used if area_name isn't already an Area in the DB.",
        )
        parser.add_argument(
            "--mode", choices=["home", "online"], default="home",
            help="'home' for a home-tuition locality page, 'online' for an "
                 "online-tuition-by-subject page (see roadmap item 25).",
        )
        parser.add_argument("--subject", default=None, help="Optional: focus the page on one subject.")
        parser.add_argument("--output", default=None, help="Output JSON file path (default: auto-named).")

    def handle(self, *args, **options):
        area_name = options["area_name"]
        city_name = options["city"]
        mode = options["mode"]
        subject = options.get("subject")

        # Prefer the real Area row if one exists (gets exact spelling,
        # pincode, city) but this command works without one too --
        # generating copy for an area Tutoro hasn't expanded into in
        # the database yet is exactly the Phase 7 SEO-expansion case.
        area = Area.objects.select_related("city").filter(name__iexact=area_name).first()
        if area:
            area_name, city_name = area.name, area.city.name

        page_kind = f"online tutoring for {subject}" if (mode == "online" and subject) else (
            "online tutoring" if mode == "online" else "home tutoring"
        )

        system = (
            "You write SEO-friendly landing page copy for Tutoro, a tutor-matching "
            "service in India. Write factual, non-hyperbolic copy -- no invented "
            "statistics, awards, testimonials, or specific prices. Respond with "
            'ONLY this JSON object: {"headline": "...", "meta_description": '
            '"under 160 chars", "intro_paragraph": "2-3 sentences", "faq": '
            '[{"question": "...", "answer": "..."}, ... 3 items]}. No markdown '
            "fences, no other keys."
        )
        user_prompt = json.dumps(
            {"area": area_name, "city": city_name, "page_type": page_kind, "subject": subject}
        )

        try:
            result = complete_json(system, user_prompt, model=SONNET_MODEL, max_tokens=1200)
        except AIUnavailableError as exc:
            raise CommandError(str(exc))
        except Exception as exc:
            raise CommandError(f"AI generation failed: {exc}")

        output_path = options["output"] or f"area_page_copy_{area_name.lower().replace(' ', '_')}_{mode}.json"
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        self.stdout.write(self.style.SUCCESS(
            f"Wrote {output_path} -- review it, then paste into a new "
            f"areas/*.html page cloned from an existing one. This does NOT "
            f"publish anything automatically."
        ))
