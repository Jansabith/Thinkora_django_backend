"""
python manage.py seed_demo                    -> demo Python and JavaScript courses with practice questions
python manage.py seed_demo --with-demo-users  -> also demo_admin and demo_student accounts

Videos are not created: add real video links yourself from the admin pages.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from courses.models import Course, Topic
from questions.models import Question
from users.models import User

DEMO_PASSWORD = 'Demo-Pass-2026'

EASY = Question.Difficulty.EASY
MEDIUM = Question.Difficulty.MEDIUM
HARD = Question.Difficulty.HARD

# Each question is (difficulty, question text, answer).
DEMO_COURSES = [
    {
        'title': 'Python',
        'description': 'Start programming with Python: variables, decisions, loops, collections and functions.',
        'category': 'Programming',
        'level': Course.Level.BEGINNER,
        'topics': [
            {
                'title': 'Variables',
                'description': 'Store values with names: strings, integers and floats.',
                'questions': [
                    (EASY, 'Create a variable called name that stores your name, then print it.', 'name = "Ali"\nprint(name)'),
                    (EASY, 'What is the difference between = and == ?', '= gives a value to a variable.\n== compares two values and gives True or False.'),
                    (MEDIUM, 'Swap the values of two variables a and b without using a third variable.', 'a, b = b, a'),
                ],
            },
            {
                'title': 'If Statements',
                'description': 'Make decisions with if, elif and else.',
                'questions': [
                    (EASY, 'Write a program that prints "Even" if a number is even and "Odd" if it is odd.', 'number = 7\nif number % 2 == 0:\n    print("Even")\nelse:\n    print("Odd")'),
                    (MEDIUM, 'Given marks, print the grade: A for 80 or more, B for 60-79, C for 40-59, otherwise F.', 'if marks >= 80:\n    print("A")\nelif marks >= 60:\n    print("B")\nelif marks >= 40:\n    print("C")\nelse:\n    print("F")'),
                    (HARD, 'Check whether a year is a leap year.', 'A year is a leap year if it is divisible by 4 and not by 100,\nor if it is divisible by 400.\n\nif (year % 4 == 0 and year % 100 != 0) or year % 400 == 0:\n    print("Leap year")\nelse:\n    print("Not a leap year")'),
                ],
            },
            {
                'title': 'Loops',
                'description': 'Repeat code with for and while loops.',
                'questions': [
                    (EASY, 'Print the numbers from 1 to 10 using a for loop.', 'for number in range(1, 11):\n    print(number)'),
                    (MEDIUM, 'Find the sum of all even numbers from 1 to 100.', 'total = 0\nfor number in range(2, 101, 2):\n    total += number\nprint(total)  # 2550'),
                    (HARD, 'Print the first 10 numbers of the Fibonacci sequence.', 'a, b = 0, 1\nfor _ in range(10):\n    print(a)\n    a, b = b, a + b'),
                ],
            },
            {
                'title': 'Lists',
                'description': 'Ordered collections you can change.',
                'questions': [
                    (EASY, 'What is a list in Python?', 'An ordered collection of items that can be changed, written in square brackets, for example [1, 2, 3].'),
                    (EASY, 'How do you add an item to the end of a list?', 'my_list.append(item)'),
                    (MEDIUM, 'What is the difference between append() and extend()?', 'append() adds ONE item (even if that item is a list).\nextend() adds EACH item from another list.\n\nnumbers = [1, 2]\nnumbers.append([3, 4])  # [1, 2, [3, 4]]\nnumbers = [1, 2]\nnumbers.extend([3, 4])  # [1, 2, 3, 4]'),
                    (HARD, 'Remove duplicates from a list but keep the original order.', 'items = [3, 1, 3, 2, 1]\nunique_items = []\nfor item in items:\n    if item not in unique_items:\n        unique_items.append(item)\nprint(unique_items)  # [3, 1, 2]'),
                ],
            },
            {
                'title': 'Tuples',
                'description': 'Ordered collections that cannot be changed.',
                'questions': [
                    (EASY, 'How is a tuple different from a list?', 'A tuple cannot be changed after it is created (it is immutable). A list can be changed.'),
                    (MEDIUM, 'Unpack the tuple point = (3, 5) into two variables x and y.', 'x, y = point'),
                ],
            },
            {
                'title': 'Dictionaries',
                'description': 'Store pairs of keys and values.',
                'questions': [
                    (EASY, 'Create a dictionary for a student with the keys name and age, then print the name.', 'student = {"name": "Ali", "age": 15}\nprint(student["name"])'),
                    (MEDIUM, 'Count how many times each word appears in a sentence.', 'sentence = "the cat and the hat"\ncounts = {}\nfor word in sentence.split():\n    counts[word] = counts.get(word, 0) + 1\nprint(counts)'),
                    (HARD, 'Given a dictionary of names and marks, print the name with the highest marks.', 'marks = {"Ali": 72, "Sara": 91, "Omar": 85}\nprint(max(marks, key=marks.get))  # Sara'),
                ],
            },
            {
                'title': 'Functions',
                'description': 'Reusable blocks of code with def and return.',
                'questions': [
                    (EASY, 'Write a function greet(name) that returns "Hello, <name>!".', 'def greet(name):\n    return f"Hello, {name}!"'),
                    (MEDIUM, 'Write a function that returns the largest number in a list without using max().', 'def largest(numbers):\n    biggest = numbers[0]\n    for number in numbers:\n        if number > biggest:\n            biggest = number\n    return biggest'),
                    (HARD, 'Write a recursive function factorial(n).', 'def factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n - 1)'),
                ],
            },
        ],
    },
    {
        'title': 'JavaScript',
        'description': 'The language of the web: variables, functions and arrays.',
        'category': 'Web Development',
        'level': Course.Level.BEGINNER,
        'topics': [
            {
                'title': 'Variables',
                'description': 'let, const and why to avoid var.',
                'questions': [
                    (EASY, 'What is the difference between let and const?', 'A let variable can be given a new value later.\nA const variable cannot be reassigned.'),
                    (MEDIUM, 'Why should you avoid var in modern JavaScript?', 'var is function-scoped and hoisted, which can cause surprising bugs.\nlet and const are block-scoped and safer.'),
                ],
            },
            {
                'title': 'Functions',
                'description': 'Function declarations and arrow functions.',
                'questions': [
                    (EASY, 'Write an arrow function add that returns the sum of two numbers.', 'const add = (a, b) => a + b'),
                    (MEDIUM, 'What does a function return if it has no return statement?', 'undefined'),
                ],
            },
            {
                'title': 'Arrays',
                'description': 'Lists of values and useful array methods.',
                'questions': [
                    (EASY, 'How do you add an item to the end of an array?', 'array.push(item)'),
                    (MEDIUM, 'Use map() to double every number in [1, 2, 3].', '[1, 2, 3].map((number) => number * 2)  // [2, 4, 6]'),
                    (HARD, 'Use reduce() to find the sum of an array of numbers.', 'const total = numbers.reduce((sum, number) => sum + number, 0)'),
                ],
            },
        ],
    },
]


class Command(BaseCommand):
    help = 'Create demo courses, topics and practice questions (and optional demo accounts).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--with-demo-users',
            action='store_true',
            help=f'Also create demo_admin and demo_student (password: {DEMO_PASSWORD}).',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['with_demo_users'] and not settings.DEBUG:
            raise CommandError('Demo users are only for development (DEBUG=True).')

        for course_data in DEMO_COURSES:
            self.create_course(course_data)

        if options['with_demo_users']:
            self.create_demo_user('demo_admin', User.Role.ADMIN, 'Demo', 'Admin')
            self.create_demo_user('demo_student', User.Role.STUDENT, 'Demo', 'Student')

    def create_course(self, course_data):
        if Course.objects.filter(title=course_data['title']).exists():
            self.stdout.write(self.style.WARNING(f'Course "{course_data["title"]}" already exists. Skipping it.'))
            return

        course = Course.objects.create(
            title=course_data['title'],
            description=course_data['description'],
            category=course_data['category'],
            level=course_data['level'],
        )
        question_total = 0

        for topic_order, topic_data in enumerate(course_data['topics'], start=1):
            topic = Topic.objects.create(
                course=course,
                title=topic_data['title'],
                description=topic_data['description'],
                order=topic_order,
            )
            for question_order, (difficulty, text, answer) in enumerate(topic_data['questions'], start=1):
                Question.objects.create(
                    topic=topic,
                    difficulty=difficulty,
                    text=text,
                    answer=answer,
                    order=question_order,
                )
                question_total += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Created "{course.title}": {len(course_data["topics"])} topics, {question_total} questions.'
            )
        )

    def create_demo_user(self, username, role, first_name, last_name):
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'User "{username}" already exists. Skipping.'))
            return
        User.objects.create_user(
            username=username,
            email=f'{username}@example.com',
            password=DEMO_PASSWORD,
            first_name=first_name,
            last_name=last_name,
            role=role,
            access_status=User.AccessStatus.APPROVED,
        )
        self.stdout.write(self.style.SUCCESS(f'Created {role} "{username}" (password: {DEMO_PASSWORD}).'))
