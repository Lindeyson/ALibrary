import datetime
import uuid

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Author, Book, BookInstance, Genre, Language


class AuthorListViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 13 авторов для проверки постраничного вывода
        number_of_authors = 13
        for author_num in range(number_of_authors):
            Author.objects.create(
                first_name='Christian %s' % author_num,
                last_name='Surname %s' % author_num,
            )

    def test_view_url_exists_at_desired_location(self):
        resp = self.client.get('/catalog/authors/')
        self.assertEqual(resp.status_code, 200)

    def test_view_url_accessible_by_name(self):
        resp = self.client.get(reverse('authors'))
        self.assertEqual(resp.status_code, 200)

    def test_view_uses_correct_template(self):
        resp = self.client.get(reverse('authors'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'catalog/author_list.html')

    def test_pagination_is_ten(self):
        resp = self.client.get(reverse('authors'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue('is_paginated' in resp.context)
        self.assertTrue(resp.context['is_paginated'] == True)
        self.assertEqual(len(resp.context['author_list']), 10)

    def test_lists_all_authors(self):
        # Вторая страница должна содержать оставшихся 3 автора
        resp = self.client.get(reverse('authors') + '?page=2')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue('is_paginated' in resp.context)
        self.assertTrue(resp.context['is_paginated'] == True)
        self.assertEqual(len(resp.context['author_list']), 3)


class LoanedBookInstancesByUserListViewTest(TestCase):
    def setUp(self):
        # Создание двух пользователей
        test_user1 = User.objects.create_user(username='testuser1', password='12345')
        test_user1.save()
        test_user2 = User.objects.create_user(username='testuser2', password='12345')
        test_user2.save()

        # Создание книги
        test_author = Author.objects.create(first_name='John', last_name='Smith')
        test_genre = Genre.objects.create(name='Fantasy')
        test_language = Language.objects.create(name='English')
        test_book = Book.objects.create(
            title='Book Title',
            summary='My book summary',
            isbn='ABCDEFG',
            author=test_author,
            language=test_language,
        )

        # Жанр назначается отдельным шагом (many-to-many нельзя присвоить напрямую)
        genre_objects_for_book = Genre.objects.all()
        test_book.genre.set(genre_objects_for_book)
        test_book.save()

        # Создание 30 объектов BookInstance
        number_of_book_copies = 30
        for book_copy in range(number_of_book_copies):
            return_date = timezone.now() + datetime.timedelta(days=book_copy % 5)
            if book_copy % 2:
                the_borrower = test_user1
            else:
                the_borrower = test_user2
            status = 'm'
            BookInstance.objects.create(
                book=test_book,
                imprint='Unlikely Imprint, 2016',
                due_back=return_date,
                borrower=the_borrower,
                status=status,
            )

    def test_redirect_if_not_logged_in(self):
        resp = self.client.get(reverse('my-borrowed'))
        self.assertRedirects(resp, '/accounts/login/?next=/catalog/mybooks/')

    def test_logged_in_uses_correct_template(self):
        self.client.login(username='testuser1', password='12345')
        resp = self.client.get(reverse('my-borrowed'))

        # Проверка, что пользователь залогинился
        self.assertEqual(str(resp.context['user']), 'testuser1')
        # Проверка ответа на запрос
        self.assertEqual(resp.status_code, 200)
        # Проверка, что используется правильный шаблон
        self.assertTemplateUsed(resp, 'catalog/bookinstance_list_borrowed_user.html')

    def test_only_borrowed_books_in_list(self):
        self.client.login(username='testuser1', password='12345')
        resp = self.client.get(reverse('my-borrowed'))

        self.assertEqual(str(resp.context['user']), 'testuser1')
        self.assertEqual(resp.status_code, 200)

        # Изначально ни одна книга не выдана (у всех статус 'm')
        self.assertTrue('bookinstance_list' in resp.context)
        self.assertEqual(len(resp.context['bookinstance_list']), 0)

        # Теперь все книги "выданы"
        get_ten_books = BookInstance.objects.all()[:10]
        for copy in get_ten_books:
            copy.status = 'o'
            copy.save()

        # Проверка, что все выданные книги в списке
        resp = self.client.get(reverse('my-borrowed'))
        self.assertEqual(str(resp.context['user']), 'testuser1')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue('bookinstance_list' in resp.context)

        # Все книги принадлежат testuser1 и имеют статус "выдана"
        for bookitem in resp.context['bookinstance_list']:
            self.assertEqual(resp.context['user'], bookitem.borrower)
            self.assertEqual('o', bookitem.status)

    def test_pages_ordered_by_due_date(self):
        # Изменение статуса на "выдана"
        for copy in BookInstance.objects.all():
            copy.status = 'o'
            copy.save()

        self.client.login(username='testuser1', password='12345')
        resp = self.client.get(reverse('my-borrowed'))

        self.assertEqual(str(resp.context['user']), 'testuser1')
        self.assertEqual(resp.status_code, 200)

        # Из всего списка показывается только 10 экземпляров
        self.assertEqual(len(resp.context['bookinstance_list']), 10)

        last_date = None
        for copy in resp.context['bookinstance_list']:
            if last_date is not None:
                self.assertTrue(last_date <= copy.due_back)
            last_date = copy.due_back


class RenewBookInstancesViewTest(TestCase):
    def setUp(self):
        # Создание пользователей
        test_user1 = User.objects.create_user(username='testuser1', password='12345')
        test_user1.save()
        test_user2 = User.objects.create_user(username='testuser2', password='12345')
        test_user2.save()
        permission = Permission.objects.get(name='Set book as returned')
        test_user2.user_permissions.add(permission)
        test_user2.save()

        # Создание книги
        test_author = Author.objects.create(first_name='John', last_name='Smith')
        test_genre = Genre.objects.create(name='Fantasy')
        test_language = Language.objects.create(name='English')
        test_book = Book.objects.create(
            title='Book Title',
            summary='My book summary',
            isbn='ABCDEFG',
            author=test_author,
            language=test_language,
        )

        # Жанр
        genre_objects_for_book = Genre.objects.all()
        test_book.genre.set(genre_objects_for_book)
        test_book.save()

        # Экземпляр книги для testuser1
        return_date = datetime.date.today() + datetime.timedelta(days=5)
        self.test_bookinstance1 = BookInstance.objects.create(
            book=test_book, imprint='Unlikely Imprint, 2016',
            due_back=return_date, borrower=test_user1, status='o',
        )

        # Экземпляр книги для testuser2
        return_date = datetime.date.today() + datetime.timedelta(days=5)
        self.test_bookinstance2 = BookInstance.objects.create(
            book=test_book, imprint='Unlikely Imprint, 2016',
            due_back=return_date, borrower=test_user2, status='o',
        )

    def test_redirect_if_not_logged_in(self):
        resp = self.client.get(reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}))
        # assertRedirects не подходит: адрес перенаправления заранее неизвестен
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.startswith('/accounts/login/'))

    def test_redirect_if_logged_in_but_not_correct_permission(self):
        self.client.login(username='testuser1', password='12345')
        resp = self.client.get(reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.startswith('/accounts/login/'))

    def test_logged_in_with_permission_borrowed_book(self):
        self.client.login(username='testuser2', password='12345')
        resp = self.client.get(reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance2.pk}))
        # Это наша книга и у нас есть нужное разрешение
        self.assertEqual(resp.status_code, 200)

    def test_logged_in_with_permission_another_users_borrowed_book(self):
        self.client.login(username='testuser2', password='12345')
        resp = self.client.get(reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}))
        # Мы библиотекарь, поэтому можем открыть чужую книгу
        self.assertEqual(resp.status_code, 200)

    def test_HTTP404_for_invalid_book_if_logged_in(self):
        test_uid = uuid.uuid4()  # маловероятный UID
        self.client.login(username='testuser2', password='12345')
        resp = self.client.get(reverse('renew-book-librarian', kwargs={'pk': test_uid}))
        self.assertEqual(resp.status_code, 404)

    def test_uses_correct_template(self):
        self.client.login(username='testuser2', password='12345')
        resp = self.client.get(reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'catalog/book_renew_librarian.html')

    def test_form_renewal_date_initially_has_date_three_weeks_in_future(self):
        self.client.login(username='testuser2', password='12345')
        resp = self.client.get(reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}))
        self.assertEqual(resp.status_code, 200)

        date_3_weeks_in_future = datetime.date.today() + datetime.timedelta(weeks=3)
        self.assertEqual(resp.context['form'].initial['renewal_date'], date_3_weeks_in_future)

    def test_redirects_to_all_borrowed_book_list_on_success(self):
        self.client.login(username='testuser2', password='12345')
        valid_date_in_future = datetime.date.today() + datetime.timedelta(weeks=2)
        resp = self.client.post(
            reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}),
            {'renewal_date': valid_date_in_future},
        )
        self.assertRedirects(resp, reverse('all-borrowed'))

    def test_form_invalid_renewal_date_past(self):
        self.client.login(username='testuser2', password='12345')
        date_in_past = datetime.date.today() - datetime.timedelta(weeks=1)
        resp = self.client.post(
            reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}),
            {'renewal_date': date_in_past},
        )
        self.assertEqual(resp.status_code, 200)
        # В современном Django assertFormError принимает саму форму, а не ответ
        self.assertFormError(resp.context['form'], 'renewal_date', 'Invalid date - renewal in past')

    def test_form_invalid_renewal_date_future(self):
        self.client.login(username='testuser2', password='12345')
        invalid_date_in_future = datetime.date.today() + datetime.timedelta(weeks=5)
        resp = self.client.post(
            reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}),
            {'renewal_date': invalid_date_in_future},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFormError(resp.context['form'], 'renewal_date', 'Invalid date - renewal more than 4 weeks ahead')


class AuthorCreateViewTest(TestCase):
    """Домашнее задание из части 10: тесты для AuthorCreate."""

    def setUp(self):
        User.objects.create_user(username='testuser1', password='12345')
        librarian = User.objects.create_user(username='testuser2', password='12345')
        librarian.user_permissions.add(Permission.objects.get(name='Set book as returned'))

    def test_redirect_if_not_logged_in(self):
        resp = self.client.get(reverse('author_create'))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.startswith('/accounts/login/'))

    def test_forbidden_if_logged_in_but_not_correct_permission(self):
        self.client.login(username='testuser1', password='12345')
        resp = self.client.get(reverse('author_create'))
        self.assertEqual(resp.status_code, 403)

    def test_logged_in_with_permission(self):
        self.client.login(username='testuser2', password='12345')
        resp = self.client.get(reverse('author_create'))
        self.assertEqual(resp.status_code, 200)

    def test_uses_correct_template(self):
        self.client.login(username='testuser2', password='12345')
        resp = self.client.get(reverse('author_create'))
        self.assertTemplateUsed(resp, 'catalog/author_form.html')

    def test_form_date_of_death_initially_set_to_expected_date(self):
        self.client.login(username='testuser2', password='12345')
        resp = self.client.get(reverse('author_create'))
        self.assertEqual(resp.context['form'].initial['date_of_death'], '12/10/2016')

    def test_redirects_to_detail_view_on_success(self):
        self.client.login(username='testuser2', password='12345')
        resp = self.client.post(reverse('author_create'), {'first_name': 'Christian', 'last_name': 'Surname'})
        author = Author.objects.get(first_name='Christian')
        self.assertRedirects(resp, author.get_absolute_url())


class AllBorrowedViewTest(TestCase):
    def setUp(self):
        User.objects.create_user(username='member', password='12345')
        librarian = User.objects.create_user(username='librarian', password='12345')
        librarian.user_permissions.add(Permission.objects.get(name='Set book as returned'))

    def test_redirect_if_not_logged_in(self):
        resp = self.client.get(reverse('all-borrowed'))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.startswith('/accounts/login/'))

    def test_forbidden_for_member_without_permission(self):
        self.client.login(username='member', password='12345')
        self.assertEqual(self.client.get(reverse('all-borrowed')).status_code, 403)

    def test_librarian_sees_page_with_correct_template(self):
        self.client.login(username='librarian', password='12345')
        resp = self.client.get(reverse('all-borrowed'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'catalog/bookinstance_list_borrowed_all.html')


class IndexViewTest(TestCase):
    def test_index_lists_new_books_with_availability(self):
        author = Author.objects.create(first_name='John', last_name='Smith')
        available_book = Book.objects.create(title='Available', summary='s', isbn='1', author=author)
        Book.objects.create(title='Missing', summary='s', isbn='2', author=author)
        BookInstance.objects.create(book=available_book, imprint='x', status='a')

        resp = self.client.get(reverse('index'))
        self.assertEqual(resp.status_code, 200)
        availability = {book.title: book.available for book in resp.context['new_books']}
        self.assertEqual(availability, {'Available': 1, 'Missing': 0})
        self.assertContains(resp, 'В наличии')
        self.assertContains(resp, 'Отсутствует')

    def test_index_shows_session_visit_counter(self):
        self.client.get(reverse('index'))
        resp = self.client.get(reverse('index'))
        self.assertEqual(resp.context['num_visits'], 1)
