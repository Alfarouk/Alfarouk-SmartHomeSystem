from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from smart_home.commands import parse, process
from smart_home.controller import CommandError, Home, Operation, validate_document


class HomeTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000.0
        self.home = Home(clock=lambda: self.now)

    def device(self, key):
        return next(d for d in self.home.snapshot()["devices"] if d["id"] == key)

    def test_default_state_is_valid_and_honestly_simulated(self):
        state = self.home.snapshot()
        self.assertEqual(len(state["devices"]), 7)
        self.assertEqual(state["mode"], "simulation")
        self.assertFalse(state["physical_hardware_connected"])
        self.assertEqual(self.device("door_1")["state"], "closed")
        self.assertTrue(self.device("door_1")["locked"])

    def test_empty_or_invalid_control_code_is_not_a_bypass(self):
        for code in ["", "x", "\n2468", None]:
            with self.assertRaises(CommandError):
                Home(code=code)

    def test_configuration_without_optional_scenes_can_manage_scenes(self):
        config = deepcopy(self.home.data)
        config.pop("scenes")
        self.assertTrue(self.home.replace_configuration(config).ok)
        self.assertEqual(self.home.snapshot()["scenes"], {})
        self.assertFalse(process(self.home, "activate scene study").ok)
        self.assertTrue(self.home.save_scene("study", [
            {"device_id": "light_1", "command": "dim", "value": 35}
        ]).ok)
        self.assertTrue(process(self.home, "activate scene study").ok)
        self.assertEqual(self.device("light_1")["brightness"], 35)

    def test_restarted_controller_has_distinct_refresh_identity(self):
        other = Home()
        self.assertEqual(other.revision, self.home.revision)
        self.assertNotEqual(other.snapshot()["instance_id"], self.home.snapshot()["instance_id"])

    def test_lights_and_room_targeting(self):
        self.assertTrue(process(self.home, "turn on the lights in Bedroom").ok)
        self.assertEqual(self.device("light_1")["state"], "off")
        self.assertEqual(self.device("light_2")["state"], "on")
        self.assertTrue(process(self.home, "dim Main Light to 30").ok)
        self.assertEqual(self.device("light_1")["brightness"], 30)
        self.assertTrue(process(self.home, "set Main Light color to blue").ok)
        self.assertEqual(self.device("light_1")["color"], "blue")

    def test_all_implemented_device_families(self):
        for text in ["set Ceiling Fan speed to 45", "open Window Curtain", "open Trash Bin"]:
            self.assertTrue(process(self.home, text).ok, text)
        self.assertEqual(self.device("fan_1")["speed"], 45)
        self.assertEqual(self.device("curtain_1")["position"], 100)
        self.assertEqual(self.device("bin_1")["state"], "open")
        self.assertTrue(process(self.home, "set Window Curtain position to 55").ok)
        self.assertEqual(self.device("curtain_1")["position"], 55)

    def test_unlock_is_not_misread_as_lock(self):
        self.assertFalse(process(self.home, "unlock Front Door").ok)
        self.assertTrue(process(self.home, "unlock Front Door", code="2468").ok)
        self.assertFalse(self.device("door_1")["locked"])

    def test_negation_and_uncertainty_do_not_execute(self):
        before = self.home.snapshot()
        for text in ["do not unlock Front Door", "don't turn on lights", "never lock doors",
                     "maybe turn off lights", "unlock door if alarm disarmed",
                     "turn on lights and open door", "lock or unlock door"]:
            self.assertFalse(process(self.home, text, code="2468").ok, text)
        self.assertEqual(self.home.snapshot(), before)

    def test_fuzzy_suggestion_does_not_act(self):
        before = self.home.snapshot()
        result = process(self.home, "trun on the ligths")
        self.assertFalse(result.ok)
        self.assertIn("No change", result.message)
        self.assertEqual(self.home.snapshot(), before)

    def test_security_interlocks_and_code(self):
        self.assertTrue(process(self.home, "arm the alarm").ok)
        self.assertFalse(process(self.home, "unlock Front Door", code="2468").ok)
        self.assertFalse(process(self.home, "disarm the alarm", code="wrong").ok)
        self.assertTrue(process(self.home, "disarm the alarm", code="2468").ok)
        self.assertTrue(process(self.home, "unlock Front Door", code="2468").ok)
        self.assertFalse(process(self.home, "arm the alarm").ok)
        self.assertTrue(process(self.home, "open Front Door").ok)
        self.assertFalse(process(self.home, "lock Front Door").ok)

    def test_auto_close_has_no_background_timer_and_does_not_autolock(self):
        process(self.home, "unlock Front Door", code="2468")
        process(self.home, "open Front Door")
        self.now += 6
        self.assertEqual(self.device("door_1")["state"], "closed")
        self.assertFalse(self.device("door_1")["locked"])
        self.assertNotIn("auto_close_at", self.device("door_1"))

    def test_help_status_have_no_state_side_effect(self):
        before = self.home.snapshot()
        for text in ["help", "?", "status", "exit"]:
            self.assertTrue(process(self.home, text).ok)
        self.assertEqual(self.home.snapshot(), before)

    def test_percentage_rejections_are_atomic(self):
        before = self.home.snapshot()
        for value in [-1, 101, True, "50", 0.5, None]:
            r = self.home.execute([Operation("light_1", "dim", value)])
            self.assertFalse(r.ok, value)
        self.assertEqual(self.home.snapshot(), before)

    def test_good_morning_movie_and_night_scenes(self):
        self.assertTrue(self.home.scene("good_morning").ok)
        self.assertEqual(self.device("curtain_1")["position"], 100)
        self.assertTrue(self.home.scene("movie_time").ok)
        self.assertEqual(self.device("light_1")["brightness"], 30)
        self.assertEqual(self.device("fan_1")["speed"], 20)
        self.assertTrue(self.home.scene("night_mode").ok)
        self.assertEqual(self.device("light_1")["state"], "off")
        self.assertEqual(self.device("fan_1")["speed"], 0)
        self.assertTrue(self.device("door_1")["locked"])

    def test_failed_scene_does_not_partially_apply(self):
        steps = [{"device_id": "light_1", "command": "turn_on"},
                 {"device_id": "light_2", "command": "dim", "value": 999}]
        self.home.data["scenes"]["broken"] = steps
        before = self.home.snapshot()
        self.assertFalse(self.home.scene("broken").ok)
        self.assertEqual(self.home.snapshot(), before)

    def test_missing_room_or_ambiguous_security_does_not_act(self):
        for text in ["turn on lights in Attic", "activate security", "disable security"]:
            self.assertFalse(process(self.home, text).ok)

    def test_persistence_and_corrupt_state_are_explicit(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / "home.json"
            home = Home(state_file=file)
            self.assertTrue(process(home, "turn on lights").ok)
            self.assertEqual(Home(state_file=file).data, home.data)
            file.write_text("{broken")
            with self.assertRaises(CommandError):
                Home(state_file=file)
            self.assertEqual(file.read_text(), "{broken")

    def test_write_failure_does_not_claim_success_or_mutate_memory(self):
        before = self.home.snapshot()
        with patch.object(self.home, "_persist", side_effect=OSError("disk full")):
            result = process(self.home, "turn on lights")
        self.assertFalse(result.ok)
        self.assertEqual(self.home.snapshot(), before)

    def test_add_remove_and_save_scene_round_trip(self):
        config = {"id": "desk", "name": "Desk Light", "room": "Office", "type": "light",
                  "state": "off", "brightness": 70, "color": "white"}
        self.assertTrue(self.home.add_device(config).ok)
        self.assertFalse(self.home.add_device(config).ok)
        self.assertTrue(self.home.save_scene("study", [{"device_id": "desk", "command": "turn_on"}]).ok)
        self.assertTrue(self.home.scene("study").ok)
        self.assertFalse(self.home.remove_device("desk").ok)
        self.assertTrue(self.home.remove_scene("study").ok)
        self.assertTrue(self.home.remove_device("desk").ok)

    def test_invalid_config_does_not_pass_as_a_valid_home(self):
        raw = deepcopy(self.home.data)
        raw["devices"][0]["brightness"] = float("nan")
        with self.assertRaises(CommandError):
            validate_document(raw)
        raw = deepcopy(self.home.data)
        raw["devices"][2]["state"] = "open"
        with self.assertRaises(CommandError):
            validate_document(raw)

    def test_empty_long_and_non_string_commands_reject(self):
        for text in ["", " " * 20, "a" * 301, None, ["turn on lights"]]:
            self.assertFalse(process(self.home, text).ok)

    def test_explicit_names_preserve_clear_unlock_and_alarm_actions(self):
        self.assertEqual(parse(self.home, "unlock Front Door").operations[0].command, "unlock")
        self.assertEqual(parse(self.home, "turn off alarm").operations[0].command, "disarm")
        self.assertEqual(parse(self.home, "turn on alarm").operations[0].command, "arm")

    def test_named_device_plus_room_and_filtered_status(self):
        self.assertTrue(process(self.home, "turn on Main Light in Living Room").ok)
        self.assertFalse(process(self.home, "turn on Main Light in Bedroom").ok)
        self.assertIn("Main Light: on", process(self.home, "status of Living Room").message)
        self.assertIn("locked", process(self.home, "status of Front Door").message)
        self.assertFalse(process(self.home, "status of Attic").ok)

    def test_config_import_is_atomic_and_does_not_expose_code(self):
        before = self.home.snapshot()
        self.assertFalse(self.home.replace_configuration({"name": "broken"}).ok)
        self.assertEqual(self.home.snapshot(), before)
        new = deepcopy(self.home.data)
        new["name"] = "My Demo"
        self.assertTrue(self.home.replace_configuration(new).ok)
        self.assertNotIn("code", self.home.snapshot())

    def test_scene_definition_does_not_execute_and_invalid_value_rejects(self):
        self.assertTrue(self.home.save_scene("unlock", [{"device_id": "door_1", "command": "unlock"}]).ok)
        self.assertTrue(self.device("door_1")["locked"])
        self.assertFalse(self.home.scene("unlock").ok)
        self.assertTrue(self.home.scene("unlock", code="2468").ok)
        self.assertFalse(self.home.save_scene("bad", [{"device_id": "light_1", "command": "dim", "value": 101}]).ok)


if __name__ == "__main__":
    unittest.main()
