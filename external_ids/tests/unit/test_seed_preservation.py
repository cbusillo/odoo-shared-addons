from odoo.tests import TransactionCase, tagged

from ...migrations.preserve_seed_records import preserve_seed_records


@tagged("post_install", "-at_install", "unit_test", "external_ids")
class TestSeedPreservation(TransactionCase):
    def test_upgrade_cleanup_keeps_seeded_system_and_existing_identity(self) -> None:
        system = self.env["external.system"].create({"name": "Legacy test system", "code": "legacy-test"})
        template = self.env["external.system.url"].create(
            {
                "name": "Legacy link",
                "code": "legacy-link",
                "system_id": system.id,
                "template": "https://configured.example.test/{id}",
            }
        )
        partner = self.env["res.partner"].create({"name": "Legacy identity owner"})
        binding = self.env["external.id"].create(
            {
                "res_model": "res.partner",
                "res_id": partner.id,
                "system_id": system.id,
                "external_id": "test-identity",
            }
        )
        xmlids = self.env["ir.model.data"].create(
            [
                {
                    "module": "external_ids",
                    "name": "legacy_test_system",
                    "model": system._name,
                    "res_id": system.id,
                },
                {
                    "module": "external_ids",
                    "name": "legacy_test_link",
                    "model": template._name,
                    "res_id": template.id,
                },
            ]
        )
        preserve_seed_records(self.env)
        preserve_seed_records(self.env)
        self.assertTrue(all(xmlids.mapped("noupdate")))
        # Exercise Odoo's actual obsolete-data cleanup, not a simulation of it.
        xmlids.write({"module": "seed_upgrade_probe"})
        self.env["ir.model.data"]._process_end(["seed_upgrade_probe"])
        self.assertEqual(binding.system_id, system)
        self.assertTrue(system.exists())
        self.assertTrue(template.exists())
        self.assertEqual(
            binding.get_url("legacy-link"),
            "https://configured.example.test/test-identity",
        )
