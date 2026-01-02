import unittest
from discord_http.utils import URL


class TestURL(unittest.TestCase):
    def setUp(self):
        self.base_url_str = "https://example.com/foo/bar.png?v=1#section"
        self.url = URL(self.base_url_str)

    def test_basic_properties(self):
        self.assertEqual(self.url.scheme, "https")
        self.assertEqual(self.url.host, "example.com")
        self.assertEqual(self.url.path, "/foo/bar.png")
        self.assertEqual(self.url.fragment, "section")
        self.assertEqual(self.url.origin, "https://example.com")

    def test_pathlib_style_properties(self):
        self.assertEqual(self.url.name, "bar.png")
        self.assertEqual(self.url.stem, "bar")
        self.assertEqual(self.url.suffix, ".png")

        # Test directory-style path
        dir_url = URL("https://example.com/assets/images/")
        self.assertEqual(dir_url.name, "images")
        self.assertEqual(dir_url.suffix, "")

    def test_query_manipulation(self):
        # Test reading query
        self.assertEqual(self.url["v"], "1")

        # Test updating (merging) query
        updated = self.url.update_query(v=2, theme="dark")
        self.assertEqual(updated["v"], "2")
        self.assertEqual(updated["theme"], "dark")

        # Test removing query parameter
        removed = updated.update_query(v=None)
        self.assertNotIn("v", removed.query)

        # Test clear_query
        cleared = self.url.clear_query()
        self.assertEqual(cleared.query, {})
        self.assertFalse("?" in str(cleared))

    def test_path_manipulation(self):
        # Test truediv (/) operator
        joined = self.url.parent / "logo.jpg"
        self.assertEqual(joined.path, "/foo/logo.jpg")

        # Test update_path with append and lstrip fix
        base = URL("https://example.com/api")
        appended = base.update_path("/v1", append=True)
        self.assertEqual(appended.path, "/api/v1")

    def test_request_uri(self):
        self.assertEqual(self.url.request_uri, "/foo/bar.png?v=1#section")

        # Test without query/fragment
        simple = URL("https://example.com/test")
        self.assertEqual(simple.request_uri, "/test")

    def test_credentials(self):
        auth_url = URL("https://example.com").update_user("admin", "password123")
        self.assertEqual(auth_url.user, "admin")
        self.assertEqual(auth_url.password, "password123")
        self.assertIn("admin:password123@", str(auth_url))

        # Test removing user
        no_auth = auth_url.update_user(None)
        self.assertIsNone(no_auth.user)
        self.assertNotIn("@", str(no_auth))

    def test_immutability(self):
        old_url = self.url.url
        self.url.update_query(test="data")
        # Ensure the original object didn't change
        self.assertEqual(self.url.url, old_url)

    def test_human_repr(self):
        encoded_url = URL("https://example.com/hello%20world")
        self.assertEqual(encoded_url.human_repr(), "https://example.com/hello world")

    def test_join(self):
        # Notice the trailing slash after 'posts'
        base = URL("https://example.com/blog/posts/")
        relative = base.join("../assets/img.png")
        self.assertEqual(relative.url, "https://example.com/blog/assets/img.png")


if __name__ == "__main__":
    unittest.main()
