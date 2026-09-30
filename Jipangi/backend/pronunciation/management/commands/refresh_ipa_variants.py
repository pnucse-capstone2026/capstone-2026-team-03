from django.core.management.base import BaseCommand
from django.db import transaction

from pronunciation.models import PracticeSentence
from pronunciation.services.sentence_ipa import SentenceIpaError, build_sentence_ipa


class Command(BaseCommand):
    help = "Refresh cached IPA and accepted IPA variants for practice sentences."

    def add_arguments(self, parser):
        parser.add_argument("--sentence-id", type=int)
        parser.add_argument("--include-inactive", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        queryset = PracticeSentence.objects.all().order_by("id")
        if options["sentence_id"]:
            queryset = queryset.filter(id=options["sentence_id"])
        if not options["include_inactive"]:
            queryset = queryset.filter(is_active=True)

        updated = 0
        failed = 0
        with transaction.atomic():
            for sentence in queryset:
                try:
                    ipa_data = build_sentence_ipa(sentence.text)
                except SentenceIpaError as exc:
                    failed += 1
                    self.stderr.write(f"{sentence.id}: {sentence.text} -> {exc}")
                    continue

                sentence.cached_ipa = ipa_data["cached_ipa"]
                sentence.cached_ipa_variants = ipa_data["cached_ipa_variants"]
                sentence.word_spans = ipa_data["word_spans"]
                sentence.source_metadata = {
                    **(sentence.source_metadata or {}),
                    "normalized_text": ipa_data["normalized_text"],
                    "g2p_pronunciation": ipa_data["g2p_pronunciation"],
                    "converter": "g2pk+kspon-korean-ipa-v1",
                    "ipa_variant_strategy": "standard+rule-lenient-korean-v1",
                    "ipa_variant_count": len(ipa_data["cached_ipa_variants"]),
                }
                sentence.save(
                    update_fields=[
                        "cached_ipa",
                        "cached_ipa_variants",
                        "word_spans",
                        "source_metadata",
                        "updated_at",
                    ]
                )
                updated += 1

            if options["dry_run"]:
                transaction.set_rollback(True)

        message = f"updated={updated} failed={failed}"
        if options["dry_run"]:
            message += " dry_run=rolled_back"
        self.stdout.write(self.style.SUCCESS(message))
