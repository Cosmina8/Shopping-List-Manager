import unittest
import os
import sys
import uuid

# Add parent directory to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from firebase_config import db
from werkzeug.security import generate_password_hash


class ShoppingListManagerTestCase(unittest.TestCase):
    """Test cases for Shopping List Manager application (Firestore version)"""

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        self.created_user_ids = []
        self.created_list_ids = []
        self.created_item_ids = []

    def tearDown(self):
        """Clean up created Firestore documents after each test"""
        for item_id in self.created_item_ids:
            try:
                db.collection("items").document(item_id).delete()
            except Exception:
                pass

        for list_id in self.created_list_ids:
            try:
                items = db.collection("items").where("list_id", "==", list_id).stream()
                for item in items:
                    db.collection("items").document(item.id).delete()

                db.collection("lists").document(list_id).delete()
            except Exception:
                pass

        for user_id in self.created_user_ids:
            try:
                lists = db.collection("lists").where("user_id", "==", user_id).stream()
                for lst in lists:
                    items = db.collection("items").where("list_id", "==", lst.id).stream()
                    for item in items:
                        db.collection("items").document(item.id).delete()

                    db.collection("lists").document(lst.id).delete()

                db.collection("users").document(user_id).delete()
            except Exception:
                pass

    def create_test_user(self, username=None, password='testpass123'):
        """Create a user directly in Firestore for testing"""
        if username is None:
            username = f"testuser_{uuid.uuid4().hex[:8]}"

        password_hash = generate_password_hash(password)
        user_ref = db.collection("users").document()
        user_ref.set({
            "username": username,
            "password_hash": password_hash,
            "created_at": "2026-04-20T12:00:00"
        })

        self.created_user_ids.append(user_ref.id)
        return {
            "id": user_ref.id,
            "username": username,
            "password": password
        }

    def create_test_list(self, user_id, name="Test List"):
        """Create a shopping list directly in Firestore for testing"""
        list_ref = db.collection("lists").document()
        list_ref.set({
            "user_id": user_id,
            "name": name,
            "created_at": "2026-04-20T12:05:00"
        })

        self.created_list_ids.append(list_ref.id)
        return {
            "id": list_ref.id,
            "name": name
        }

    def create_test_item(
        self,
        list_id,
        name="lapte",
        qty=2,
        unit="L",
        category="lactate",
        price=10.5,
        purchased=False
    ):
        """Create an item directly in Firestore for testing"""
        item_ref = db.collection("items").document()
        item_ref.set({
            "list_id": list_id,
            "name": name,
            "qty": qty,
            "unit": unit,
            "category": category,
            "price": price,
            "purchased": purchased,
            "created_at": "2026-04-20T12:10:00"
        })

        self.created_item_ids.append(item_ref.id)
        return {
            "id": item_ref.id,
            "name": name,
            "qty": qty,
            "unit": unit,
            "category": category,
            "price": price,
            "purchased": purchased
        }

    # -------------------------
    # Index / Auth tests
    # -------------------------

    def test_index_redirects_when_logged_in(self):
        """Logged-in users should be redirected from index to dashboard"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = "test_user_id"

        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard', response.location)

    def test_index_shows_page_when_not_logged_in(self):
        """Index page should load for anonymous users"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_register_get(self):
        """GET /register should return 200"""
        response = self.client.get('/register')
        self.assertEqual(response.status_code, 200)

    def test_register_post_success(self):
        """Successful registration should create user and redirect to login"""
        username = f"reguser_{uuid.uuid4().hex[:8]}"

        response = self.client.post('/register', data={
            'username': username,
            'password': 'testpass123'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'login', response.data.lower())

        docs = db.collection("users").where("username", "==", username).limit(1).stream()
        found_user = None
        for doc in docs:
            found_user = doc
            self.created_user_ids.append(doc.id)
            break

        self.assertIsNotNone(found_user)

    def test_register_post_missing_credentials(self):
        """Registration with missing fields should fail"""
        response = self.client.post('/register', data={
            'username': '',
            'password': 'testpass123'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'register', response.data.lower())

    def test_register_duplicate_username(self):
        """Registration with duplicate username should fail"""
        user = self.create_test_user()

        response = self.client.post('/register', data={
            'username': user['username'],
            'password': 'anotherpass123'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'register', response.data.lower())

    def test_login_get(self):
        """GET /login should return 200"""
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)

    def test_login_success(self):
        """Valid credentials should log the user in"""
        user = self.create_test_user(password='testpass123')

        response = self.client.post('/login', data={
            'username': user['username'],
            'password': 'testpass123'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'dashboard', response.data.lower())

    def test_login_sets_session(self):
        """Successful login should store user info in session"""
        user = self.create_test_user(password='testpass123')

        self.client.post('/login', data={
            'username': user['username'],
            'password': 'testpass123'
        }, follow_redirects=True)

        with self.client.session_transaction() as sess:
            self.assertIn('user_id', sess)
            self.assertEqual(sess.get('username'), user['username'])

    def test_login_wrong_password(self):
        """Wrong password should not log user in"""
        user = self.create_test_user(password='correctpass')

        response = self.client.post('/login', data={
            'username': user['username'],
            'password': 'wrongpass'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'login', response.data.lower())

    def test_logout(self):
        """Logout should clear session"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = "test_user_id"
            sess['username'] = "testuser"

        self.client.get('/logout', follow_redirects=True)

        with self.client.session_transaction() as sess:
            self.assertNotIn('user_id', sess)
            self.assertNotIn('username', sess)

    # -------------------------
    # Dashboard / List tests
    # -------------------------

    def test_dashboard_requires_login(self):
        """Dashboard should require login"""
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)

    def test_dashboard_shows_lists(self):
        """Dashboard should show the user's shopping lists"""
        user = self.create_test_user()
        self.create_test_list(user["id"], "Test List")

        with self.client.session_transaction() as sess:
            sess['user_id'] = user["id"]
            sess['username'] = user["username"]

        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Test List', response.data)

    def test_create_list(self):
        """Logged-in user should be able to create list"""
        user = self.create_test_user()

        with self.client.session_transaction() as sess:
            sess['user_id'] = user["id"]
            sess['username'] = user["username"]

        response = self.client.post('/lists/create', data={'name': 'My List'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        docs = db.collection("lists").where("user_id", "==", user["id"]).where("name", "==", "My List").stream()
        found_list = None
        for doc in docs:
            found_list = doc
            self.created_list_ids.append(doc.id)
            break

        self.assertIsNotNone(found_list)

    def test_create_list_requires_login(self):
        """Creating a list without login should redirect to login"""
        response = self.client.post('/lists/create', data={'name': 'My List'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)

    def test_create_list_empty_name(self):
        """Creating a list with empty name should not create list"""
        user = self.create_test_user()

        with self.client.session_transaction() as sess:
            sess['user_id'] = user["id"]
            sess['username'] = user["username"]

        response = self.client.post('/lists/create', data={'name': ''}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        docs = list(
            db.collection("lists")
            .where("user_id", "==", user["id"])
            .where("name", "==", "")
            .stream()
        )
        self.assertEqual(len(docs), 0)

    def test_delete_list(self):
        """User should be able to delete own list"""
        user = self.create_test_user()
        shopping_list = self.create_test_list(user["id"], "Delete Me")

        with self.client.session_transaction() as sess:
            sess['user_id'] = user["id"]
            sess['username'] = user["username"]

        response = self.client.post(f'/lists/{shopping_list["id"]}/delete', follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        deleted_doc = db.collection("lists").document(shopping_list["id"]).get()
        self.assertFalse(deleted_doc.exists)

    def test_edit_list(self):
        """User should be able to rename own list"""
        user = self.create_test_user()
        shopping_list = self.create_test_list(user["id"], "Old Name")

        with self.client.session_transaction() as sess:
            sess['user_id'] = user["id"]
            sess['username'] = user["username"]

        response = self.client.post(
            f'/lists/{shopping_list["id"]}/edit',
            data={'name': 'New Name'},
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)

        updated_doc = db.collection("lists").document(shopping_list["id"]).get()
        self.assertTrue(updated_doc.exists)
        self.assertEqual(updated_doc.to_dict().get("name"), "New Name")

    def test_view_list_requires_login(self):
        """Viewing list without login should redirect"""
        response = self.client.get('/lists/some_list_id')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)

    def test_view_list_shows_items(self):
        """Viewing a list should show its items"""
        user = self.create_test_user()
        shopping_list = self.create_test_list(user["id"], "Groceries")
        self.create_test_item(shopping_list["id"], name="lapte")

        with self.client.session_transaction() as sess:
            sess['user_id'] = user["id"]
            sess['username'] = user["username"]

        response = self.client.get(f'/lists/{shopping_list["id"]}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'lapte', response.data)

    def test_404_page(self):
        """Non-existing route should return 404"""
        response = self.client.get('/this-route-does-not-exist')
        self.assertEqual(response.status_code, 404)

    # -------------------------
    # Item / Product tests
    # -------------------------

    def test_add_item_requires_login(self):
        """Adding item without login should redirect"""
        response = self.client.post('/lists/fake_list_id/add', data={
            'name': 'lapte',
            'qty': '2',
            'unit': 'L',
            'category': 'lactate',
            'price': '10.5'
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)

    def test_add_item(self):
        """Logged-in user should be able to add item"""
        user = self.create_test_user()
        shopping_list = self.create_test_list(user["id"], "Groceries")

        with self.client.session_transaction() as sess:
            sess['user_id'] = user["id"]
            sess['username'] = user["username"]

        response = self.client.post(f'/lists/{shopping_list["id"]}/add', data={
            'name': 'lapte',
            'qty': '2',
            'unit': 'L',
            'category': 'lactate',
            'price': '10.5'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)

        docs = db.collection("items") \
            .where("list_id", "==", shopping_list['id']) \
            .where("name", "==", "lapte") \
            .limit(1) \
            .stream()

        found_item = None
        for doc in docs:
            found_item = doc
            self.created_item_ids.append(doc.id)
            break

        self.assertIsNotNone(found_item)

    def test_add_item_empty_name(self):
        """Adding item with empty name should fail"""
        user = self.create_test_user()
        shopping_list = self.create_test_list(user["id"], "Groceries")

        with self.client.session_transaction() as sess:
            sess['user_id'] = user["id"]
            sess['username'] = user["username"]

        response = self.client.post(f'/lists/{shopping_list["id"]}/add', data={
            'name': '',
            'qty': '2',
            'unit': 'L',
            'category': 'lactate',
            'price': '10.5'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)

        docs = list(
            db.collection("items")
            .where("list_id", "==", shopping_list["id"])
            .where("name", "==", "")
            .stream()
        )
        self.assertEqual(len(docs), 0)

    def test_add_item_invalid_qty(self):
        """Adding item with invalid quantity should fail"""
        user = self.create_test_user()
        shopping_list = self.create_test_list(user["id"], "Groceries")

        with self.client.session_transaction() as sess:
            sess['user_id'] = user["id"]
            sess['username'] = user["username"]

        response = self.client.post(f'/lists/{shopping_list["id"]}/add', data={
            'name': 'lapte',
            'qty': 'abc',
            'unit': 'L',
            'category': 'lactate',
            'price': '10.5'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)

        docs = list(
            db.collection("items")
            .where("list_id", "==", shopping_list["id"])
            .where("name", "==", "lapte")
            .stream()
        )
        self.assertEqual(len(docs), 0)

    def test_add_item_invalid_price(self):
        """Adding item with invalid price should fail"""
        user = self.create_test_user()
        shopping_list = self.create_test_list(user["id"], "Groceries")

        with self.client.session_transaction() as sess:
            sess['user_id'] = user["id"]
            sess['username'] = user["username"]

        response = self.client.post(f'/lists/{shopping_list["id"]}/add', data={
            'name': 'lapte',
            'qty': '2',
            'unit': 'L',
            'category': 'lactate',
            'price': 'abc'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)

        docs = list(
            db.collection("items")
            .where("list_id", "==", shopping_list["id"])
            .where("name", "==", "lapte")
            .stream()
        )
        self.assertEqual(len(docs), 0)

    def test_edit_item(self):
        """User should be able to edit item"""
        user = self.create_test_user()
        shopping_list = self.create_test_list(user["id"], "Groceries")
        item = self.create_test_item(shopping_list["id"], name="lapte", qty=2, price=10.5)

        with self.client.session_transaction() as sess:
            sess['user_id'] = user["id"]
            sess['username'] = user["username"]

        response = self.client.post(f'/items/{item["id"]}/edit', data={
            'name': 'lapte bio',
            'qty': '3',
            'unit': 'L',
            'category': 'lactate',
            'price': '15.0'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)

        updated_doc = db.collection("items").document(item["id"]).get()
        self.assertTrue(updated_doc.exists)

        updated_data = updated_doc.to_dict()
        self.assertEqual(updated_data.get("name"), "lapte bio")
        self.assertEqual(updated_data.get("qty"), 3.0)
        self.assertEqual(updated_data.get("price"), 15.0)

    def test_delete_item(self):
        """User should be able to delete item"""
        user = self.create_test_user()
        shopping_list = self.create_test_list(user["id"], "Groceries")
        item = self.create_test_item(shopping_list["id"], name="paine")

        with self.client.session_transaction() as sess:
            sess['user_id'] = user["id"]
            sess['username'] = user["username"]

        response = self.client.post(f'/items/{item["id"]}/delete', follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        deleted_doc = db.collection("items").document(item["id"]).get()
        self.assertFalse(deleted_doc.exists)

    def test_mark_item_done(self):
        """User should be able to toggle purchased status"""
        user = self.create_test_user()
        shopping_list = self.create_test_list(user["id"], "Groceries")
        item = self.create_test_item(shopping_list["id"], name="oua", purchased=False)

        with self.client.session_transaction() as sess:
            sess['user_id'] = user["id"]
            sess['username'] = user["username"]

        response = self.client.post(f'/items/{item["id"]}/toggle', follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        updated_doc = db.collection("items").document(item["id"]).get()
        self.assertTrue(updated_doc.exists)

        updated_data = updated_doc.to_dict()
        self.assertTrue(updated_data.get("purchased", False))

    def test_export_csv(self):
        """CSV export should return a downloadable CSV file"""
        user = self.create_test_user()
        shopping_list = self.create_test_list(user["id"], "Groceries")
        self.create_test_item(shopping_list["id"], name="lapte", qty=2, unit="L", price=10.5)

        with self.client.session_transaction() as sess:
            sess['user_id'] = user["id"]
            sess['username'] = user["username"]

        response = self.client.get(f'/lists/{shopping_list["id"]}/export.csv')
        self.assertEqual(response.status_code, 200)

        self.assertTrue(
            'text/csv' in response.content_type or
            'application/vnd.ms-excel' in response.content_type
        )

    def test_export_csv_requires_login(self):
        """CSV export without login should redirect"""
        response = self.client.get('/lists/fake_list_id/export.csv')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)


if __name__ == '__main__':
    unittest.main()