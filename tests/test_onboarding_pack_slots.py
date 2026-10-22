"""Onboarding fills pack-owned slots from their stubs (pixeloven/crew#96).

Synthetic packs and stubs only: discoverable and optional section markers, an
unfilled pack slot, and a partial local fill Doctor reports as DEGRADED.
"""

import json
import pathlib
import tempfile
import unittest

from scripts.check_skills import stub_sections, validate_root
from scripts.crew_doctor import (
    compose_doctor_report,
    declared_local_slots,
    inspect_installations,
    inspect_packs,
    render_doctor_report,
    slot_fills,
)
from scripts.onboarding_contract import (
    HostApplyAuthorizationSignal,
    pack_slot_proposals,
    resolve_mode,
)


DESCRIPTION = "Use when exercising the onboarding pack-slot fixture so this description comfortably clears the schema-v2 minimum."

TRACKER_STUB = """---
name: <project>-tracker-fields
description: The tracker fields <Project> files work items with.
---

Which fields a work item carries here.

## Fields

<!-- crew:discoverable capability=mcp:tracker -->

> **▸ Fill:** each field, its type, and whether it is required.

## Owners

> **▸ Fill:** who owns the tracker configuration.

## Escalation

<!-- crew:optional -->

> **▸ Fill:** where a blocked item goes.

## Notes

Nothing to fill here.

```markdown
## Not a heading
<!-- crew:optional -->
```
"""

TOPOLOGY_STUB = """---
name: <project>-topology
description: Topology.
---

## Nodes

> **▸ Fill:** nodes and addresses.
"""


def write_skill(root: pathlib.Path, name: str, extra: str = "", requires: str = "[]", body: str = "") -> pathlib.Path:
    skill = root / "skills" / name / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(
        f"---\nname: {name}\ndescription: {DESCRIPTION}\ntier: subject\n"
        f"requires: {requires}\n{extra}---\n\n# {name}\n{body}",
        encoding="utf-8",
    )
    return skill


def write_manifest(root: pathlib.Path, name: str, version: str = "1.0.0") -> None:
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".claude-plugin/plugin.json").write_text(
        json.dumps({"name": name, "version": version, "skills": "./skills"}), encoding="utf-8"
    )


def write_stub(root: pathlib.Path, slot: str, text: str) -> pathlib.Path:
    stub = root / "templates/local-skills" / f"{slot}.md"
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_text(text, encoding="utf-8")
    return stub


def write_tracker_pack(root: pathlib.Path, name: str = "example-skills", stub: str | None = TRACKER_STUB) -> None:
    write_manifest(root, name)
    (root / "slots.txt").write_text("tracker-fields\n", encoding="utf-8")
    if stub is not None:
        write_stub(root, "tracker-fields", stub)
    write_skill(root, "pack-triage", "expects-local: [tracker-fields]\n", "[plugin:crew@>=0.45.0]")


class World:
    """A crew install, a project, and any number of packs, read the way the inventory reads them."""

    def __init__(self, base: pathlib.Path) -> None:
        self.base = base
        self.crew = base / "crew"
        write_manifest(self.crew, "crew", "0.46.0")
        write_skill(self.crew, "crew-skill", "expects-local: [topology, agent-runtime]\n")
        write_stub(self.crew, "topology", TOPOLOGY_STUB)
        write_stub(self.crew, "agent-runtime", "## Runtime\n\n▸ Fill\n")
        self.project = base / "project"
        self.local = self.project / ".agents/skills"
        self.local.mkdir(parents=True)
        self.pack_roots: list[pathlib.Path] = []

    def pack(self, name: str = "example-skills", stub: str | None = TRACKER_STUB) -> pathlib.Path:
        root = self.base / name
        write_tracker_pack(root, name, stub)
        self.pack_roots.append(root)
        return root

    def inventory(self) -> dict:
        packs = inspect_packs(self.pack_roots, self.crew)
        declared = declared_local_slots(self.crew, packs=packs)
        fills = slot_fills(declared["declared"], local_roots=[self.local], packs=packs)
        return {
            "project_root": str(self.project),
            "packs": packs,
            "slots": {
                "slots": fills["slots"],
                "inspection_sources": fills["inspection_sources"],
                "pack_slots": declared["pack_slots"],
                "collisions": declared["collisions"],
            },
        }

    def proposals(self, contract=None, **kwargs) -> dict:
        found = pack_slot_proposals(self.inventory(), contract or resolve_mode(), crew_root=self.crew, **kwargs)
        return {proposal["slot"]: proposal for proposal in found}


def apply_contract():
    signal = HostApplyAuthorizationSignal(invocation_id="run-96", host_verified=True)
    return resolve_mode(explicit_apply=True, invocation_id="run-96", authorization=signal)


class StubSectionGrammarTests(unittest.TestCase):
    def test_sections_carry_markers_and_fill_state(self) -> None:
        sections, errors = stub_sections(TRACKER_STUB)
        self.assertEqual([], errors)
        self.assertEqual(
            [
                ("Fields", "mcp:tracker", False, True),
                ("Owners", None, False, True),
                ("Escalation", None, True, True),
                ("Notes", None, False, False),
            ],
            [(s["heading"], s["discoverable"], s["optional"], s["unfilled"]) for s in sections],
        )

    def test_marker_errors_are_reported_not_guessed(self) -> None:
        cases = {
            "## A\n<!-- crew:discoverable capability=tracker -->\n": "capability",
            "## A\n<!-- crew:discoverable capability=plugin:crew@>=0.1.0 -->\n": "capability",
            "## A\n<!-- crew:discoverable capability=mcp:a capability=mcp:b -->\n": "malformed",
            "## A\n<!-- crew:discoverable capability=mcp:a -->\n<!-- crew:discoverable capability=mcp:a -->\n": "repeats",
            "<!-- crew:optional -->\n## A\n": "before",
            "## A\n<!-- crew:optional please -->\n": "malformed",
        }
        for text, needle in cases.items():
            with self.subTest(text=text):
                _, errors = stub_sections(text)
                self.assertEqual(1, len(errors), errors)
                self.assertIn(needle, errors[0])

    def test_several_discoverable_markers_mean_any_of_these_sources(self) -> None:
        sections, errors = stub_sections(
            "## A\n<!-- crew:discoverable capability=mcp:warehouse -->\n"
            "<!-- crew:discoverable capability=mcp:analytics -->\n> **▸ Fill:** events.\n"
        )
        self.assertEqual([], errors)
        self.assertEqual(["mcp:warehouse", "mcp:analytics"], sections[0]["capabilities"])
        self.assertEqual("mcp:warehouse", sections[0]["discoverable"])

    def test_every_capability_kind_in_the_requires_vocabulary_is_accepted(self) -> None:
        for capability in ("mcp:tracker", "cli:gh", "external:github", "external:web", "cluster"):
            with self.subTest(capability=capability):
                sections, errors = stub_sections(f"## A\n<!-- crew:discoverable capability={capability} -->\n")
                self.assertEqual([], errors)
                self.assertEqual(capability, sections[0]["discoverable"])

    def test_pack_check_fails_a_stub_with_a_bad_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = pathlib.Path(tmp) / "pack"
            write_tracker_pack(pack)
            self.assertEqual([], validate_root(pack, pack=True))
            write_stub(pack, "tracker-fields", "## Fields\n<!-- crew:discoverable capability=tracker -->\n")
            errors = validate_root(pack, pack=True)
            self.assertEqual(1, len(errors), errors)
            self.assertIn("templates/local-skills/tracker-fields.md", errors[0])


class PackSlotProposalTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.world = World(pathlib.Path(tmp.name).resolve())

    def test_unfilled_pack_slot_is_proposed_from_the_owning_packs_stub(self) -> None:
        pack = self.world.pack()
        proposal = self.world.proposals()["tracker-fields"]
        self.assertEqual("create", proposal["action"])
        self.assertEqual("example-skills", proposal["pack"])
        self.assertEqual(str(pack / "templates/local-skills/tracker-fields.md"), proposal["stub"])
        self.assertEqual(
            str(self.world.project / ".agents/skills/project-tracker-fields/SKILL.md"), proposal["target"]
        )
        self.assertEqual([{"heading": "Fields", "capability": "mcp:tracker", "capabilities": ["mcp:tracker"]}], proposal["discoverable_sections"])
        self.assertEqual(["Owners"], proposal["human_sections"])
        self.assertEqual(["Escalation"], proposal["deferred_sections"])
        self.assertEqual("scaffold", proposal["depth"])
        self.assertIn("+name: project-tracker-fields", proposal["diff"])
        self.assertIsNone(proposal["text"], "audit never carries text to write")

    def test_deepen_asks_every_section(self) -> None:
        self.world.pack()
        proposal = self.world.proposals(depth="deepen")["tracker-fields"]
        self.assertEqual(["Owners", "Escalation"], proposal["human_sections"])
        self.assertEqual([], proposal["deferred_sections"])
        with self.assertRaises(ValueError):
            self.world.proposals(depth="thorough")

    def test_apply_returns_text_and_writes_nothing(self) -> None:
        self.world.pack()
        proposal = self.world.proposals(apply_contract())["tracker-fields"]
        self.assertIn("name: project-tracker-fields", proposal["text"])
        self.assertIn("The tracker fields project files", proposal["text"])
        self.assertIn("<!-- crew:discoverable capability=mcp:tracker -->", proposal["text"])
        self.assertFalse((self.world.local / "project-tracker-fields").exists())

    def test_crew_slot_uses_crews_stub_and_agent_runtime_is_left_to_the_capability_map(self) -> None:
        proposals = self.world.proposals()
        topology = proposals["topology"]
        self.assertIsNone(topology["pack"])
        self.assertEqual(str(self.world.crew / "templates/local-skills/topology.md"), topology["stub"])
        self.assertEqual(["Nodes"], topology["human_sections"])
        self.assertNotIn("agent-runtime", proposals)

    def test_filled_slots_are_not_proposed_and_partial_fills_are_completed(self) -> None:
        self.world.pack()
        write_skill(self.world.local.parent, "project-topology", body="\n## Nodes\n\nnode-1 10.0.0.1\n")
        partial = TRACKER_STUB.replace("<project>", "project").replace(
            "> **▸ Fill:** who owns the tracker configuration.", "The platform team."
        )
        target = self.world.local / "project-tracker-fields/SKILL.md"
        target.parent.mkdir(parents=True)
        target.write_text(partial, encoding="utf-8")
        proposals = self.world.proposals()
        self.assertNotIn("topology", proposals)
        tracker = proposals["tracker-fields"]
        self.assertEqual("complete", tracker["action"])
        self.assertEqual(str(target), tracker["target"])
        self.assertEqual([{"heading": "Fields", "capability": "mcp:tracker", "capabilities": ["mcp:tracker"]}], tracker["discoverable_sections"])
        self.assertEqual([], tracker["human_sections"])
        self.assertEqual(["Escalation"], tracker["deferred_sections"])
        self.assertIsNone(self.world.proposals(apply_contract())["tracker-fields"]["text"],
                          "completing a fill is the interview's edit, never a generated rewrite")

    def test_a_pack_fill_is_not_proposed(self) -> None:
        self.world.pack()
        filler = self.world.base / "filler"
        write_manifest(filler, "filler-skills")
        write_skill(filler, "fills-tracker", "provides: [tracker-fields]\n", "[plugin:crew@>=0.45.0]")
        self.world.pack_roots.append(filler)
        self.assertNotIn("tracker-fields", self.world.proposals())

    def test_ambiguous_owner_or_missing_stub_is_a_decision(self) -> None:
        self.world.pack("first-skills")
        self.world.pack("second-skills")
        collided = self.world.proposals()["tracker-fields"]
        self.assertEqual("decision-needed", collided["action"])
        self.assertIn("first-skills", collided["reason"])
        self.assertIsNone(collided["stub"])

        self.world.pack_roots.clear()
        self.world.pack("stubless-skills", stub=None)
        missing = self.world.proposals(apply_contract())["tracker-fields"]
        self.assertEqual("decision-needed", missing["action"])
        self.assertIn("no stub", missing["reason"])
        self.assertIsNone(missing["text"])


class DoctorPartialFillTests(unittest.TestCase):
    def test_a_fill_still_carrying_fill_markers_is_degraded_partial(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            world = World(pathlib.Path(tmp).resolve())
            world.pack()
            fill = world.local / "project-tracker-fields/SKILL.md"
            fill.parent.mkdir(parents=True)
            fill.write_text(TRACKER_STUB.replace("<project>", "project"), encoding="utf-8")
            write_skill(world.local.parent, "project-topology", body="\n## Nodes\n\nnode-1\n")
            packs = inspect_packs(world.pack_roots, world.crew)
            slots = declared_local_slots(world.crew, packs=packs)
            fills = slot_fills(slots["declared"], local_roots=[world.local], packs=packs)
            self.assertEqual(
                ["Fields", "Owners", "Escalation"],
                fills["slots"]["tracker-fields"]["local"][0]["unfilled_sections"],
            )
            before = {path: path.stat().st_mtime_ns for path in world.base.rglob("*")}
            report = compose_doctor_report(
                inspect_installations(world.project, world.base / "home"),
                runtime_comparisons=[],
                local_slots=slots,
                role_postures=[],
                persona_evidence=[],
                slot_fills=fills,
                packs=packs,
            )
            render_doctor_report(report)
            self.assertEqual(before, {path: path.stat().st_mtime_ns for path in world.base.rglob("*")})
            rows = {row["check"]: row for row in report["checks"]}
            row = rows["local-slots.fill.tracker-fields"]
            self.assertEqual("DEGRADED", row["status"])
            self.assertIn("partial", row["fact"])
            for heading in ("`Fields`", "`Owners`", "`Escalation`"):
                self.assertIn(heading, row["fact"])
            self.assertIn("onboarding", row["recommendation"])
            self.assertEqual("OK", rows["local-slots.fill.topology"]["status"])


if __name__ == "__main__":
    unittest.main()
