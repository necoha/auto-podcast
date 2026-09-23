import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from rss_feed_generator import ITUNES_NS, RSSFeedGenerator


JST = timezone(timedelta(hours=9))


class RSSFeedGeneratorTests(unittest.TestCase):
    def test_same_day_episode_reuses_number_and_replaces_item(self):
        with tempfile.TemporaryDirectory() as feed_dir:
            generator = RSSFeedGenerator(
                base_url="https://example.com",
                feed_dir=feed_dir,
                podcast_title="Test Podcast",
                podcast_description="Test Description",
                podcast_image_url="https://example.com/cover.jpg",
                episodes_subdir="episodes",
            )
            pub_date = datetime(2026, 9, 23, 8, 0, tzinfo=JST)

            self.assertEqual(generator.get_episode_number(pub_date.date()), 1)
            generator.add_episode(
                mp3_filename="episode_1_first.mp3",
                title="First",
                description="First episode",
                episode_number=1,
                duration_seconds=60,
                pub_date=pub_date,
                mp3_size=100,
            )
            self.assertEqual(generator.get_episode_number(pub_date.date()), 1)

            generator.add_episode(
                mp3_filename="episode_1_replacement.mp3",
                title="Replacement",
                description="Replacement episode",
                episode_number=1,
                duration_seconds=90,
                pub_date=pub_date.replace(hour=12),
                mp3_size=200,
            )

            channel = ET.parse(generator.feed_path).find("channel")
            self.assertIsNotNone(channel)
            items = channel.findall("item") if channel is not None else []
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].findtext("title"), "Replacement")
            self.assertEqual(
                items[0].find("enclosure").get("url"),
                "https://example.com/episodes/episode_1_replacement.mp3",
            )
            self.assertEqual(
                items[0].findtext(f"{{{ITUNES_NS}}}episode"),
                "1",
            )
            self.assertEqual(
                generator.get_episode_number(pub_date.date() + timedelta(days=1)),
                2,
            )

    def test_existing_same_day_duplicates_collapse_to_highest_number(self):
        with tempfile.TemporaryDirectory() as feed_dir:
            generator = RSSFeedGenerator(
                base_url="https://example.com",
                feed_dir=feed_dir,
                podcast_title="Test Podcast",
                podcast_description="Test Description",
                podcast_image_url="https://example.com/cover.jpg",
                episodes_subdir="episodes",
            )
            pub_date = datetime(2026, 9, 23, 8, 0, tzinfo=JST)
            generator.add_episode(
                mp3_filename="episode_1.mp3",
                title="Episode 1",
                description="First run",
                episode_number=1,
                duration_seconds=60,
                pub_date=pub_date,
                mp3_size=100,
            )

            tree = ET.parse(generator.feed_path)
            channel = tree.find("channel")
            self.assertIsNotNone(channel)
            duplicate = generator._create_item_element(
                mp3_filename="episode_2.mp3",
                title="Episode 2",
                description="Second run",
                episode_number=2,
                duration_seconds=60,
                pub_date=pub_date.replace(hour=10),
                mp3_size=100,
            )
            channel.append(duplicate)
            tree.write(generator.feed_path, encoding="unicode", xml_declaration=True)

            self.assertEqual(generator.get_episode_number(pub_date.date()), 2)
            generator.add_episode(
                mp3_filename="episode_2_final.mp3",
                title="Episode 2 Final",
                description="Final run",
                episode_number=2,
                duration_seconds=90,
                pub_date=pub_date.replace(hour=12),
                mp3_size=200,
            )

            final_channel = ET.parse(generator.feed_path).find("channel")
            self.assertIsNotNone(final_channel)
            items = final_channel.findall("item") if final_channel is not None else []
            self.assertEqual(len(items), 1)
            self.assertEqual(
                items[0].findtext(f"{{{ITUNES_NS}}}episode"),
                "2",
            )
            self.assertEqual(items[0].findtext("title"), "Episode 2 Final")


if __name__ == "__main__":
    unittest.main()