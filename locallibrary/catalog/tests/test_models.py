from django.test import TestCase

from catalog.models import Author, Genre, Book, BookInstance


class AuthorModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Author.objects.create(first_name='Big', last_name='Bob')

    def test_first_name_label(self):
        author = Author.objects.get(id=1)
        field_label = author._meta.get_field('first_name').verbose_name
        self.assertEqual(field_label, 'first name')

    def test_last_name_label(self):
        author = Author.objects.get(id=1)
        field_label = author._meta.get_field('last_name').verbose_name
        self.assertEqual(field_label, 'last name')

    def test_date_of_birth_label(self):
        author = Author.objects.get(id=1)
        field_label = author._meta.get_field('date_of_birth').verbose_name
        self.assertEqual(field_label, 'date of birth')

    def test_date_of_death_label(self):
        author = Author.objects.get(id=1)
        field_label = author._meta.get_field('date_of_death').verbose_name
        self.assertEqual(field_label, 'died')

    def test_first_name_max_length(self):
        author = Author.objects.get(id=1)
        max_length = author._meta.get_field('first_name').max_length
        self.assertEqual(max_length, 100)

    def test_last_name_max_length(self):
        author = Author.objects.get(id=1)
        max_length = author._meta.get_field('last_name').max_length
        self.assertEqual(max_length, 100)

    def test_object_name_is_last_name_comma_first_name(self):
        author = Author.objects.get(id=1)
        expected_object_name = '%s, %s' % (author.last_name, author.first_name)
        self.assertEqual(expected_object_name, str(author))

    def test_get_absolute_url(self):
        author = Author.objects.get(id=1)
        self.assertEqual(author.get_absolute_url(), '/catalog/author/1/')


class GenreModelTest(TestCase):
    def test_object_name_is_name(self):
        genre = Genre.objects.create(name='Фэнтези')
        self.assertEqual(str(genre), 'Фэнтези')


class BookModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        author = Author.objects.create(first_name='John', last_name='Smith')
        cls.book = Book.objects.create(
            title='Book Title', summary='My book summary',
            isbn='ABCDEFG', author=author,
        )

    def test_object_name_is_title(self):
        self.assertEqual(str(self.book), 'Book Title')

    def test_get_absolute_url(self):
        self.assertEqual(self.book.get_absolute_url(), '/catalog/book/%s/' % self.book.id)


class BookInstanceModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        author = Author.objects.create(first_name='John', last_name='Smith')
        book = Book.objects.create(
            title='Book Title', summary='My book summary',
            isbn='ABCDEFG', author=author,
        )
        cls.copy = BookInstance.objects.create(book=book, imprint='Imprint, 2016')

    def test_default_status_is_maintenance(self):
        self.assertEqual(self.copy.status, 'm')

    def test_is_overdue_false_without_due_back(self):
        self.assertFalse(self.copy.is_overdue)