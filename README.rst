=============================
Django plans payments
=============================

.. image:: https://badge.fury.io/py/django-plans-payments.svg
    :target: https://badge.fury.io/py/django-plans-payments

.. image:: https://travis-ci.org/PetrDlouhy/django-plans-payments.svg?branch=master
    :target: https://travis-ci.org/PetrDlouhy/django-plans-payments

.. image:: https://codecov.io/gh/PetrDlouhy/django-plans-payments/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/PetrDlouhy/django-plans-payments

Integration between `django-plans <https://github.com/django-getpaid/django-plans>`_ and `django-payments <https://github.com/mirumee/django-payments>`_.

Documentation
-------------

The full documentation is at https://django-plans-payments.readthedocs.io.

Quickstart
----------

Install and configure ``django-plans`` and ``django-payments`` apps.
Capture mode is not yet supported, so ``PAYMENT_VARINANTS`` with ``'capture': False`` will not get confirmed.

Install Django plans payments::

    pip install django-plans-payments

Add it to your ``INSTALLED_APPS``, before the ``plans``:

.. code-block:: python

    INSTALLED_APPS = (
        ...
        'plans_payments',
        'plans',
        ...
    )

Add Django ``plans_payments`` to the URL patterns:

.. code-block:: python

    urlpatterns = [
        ...
        url(r'^plans-payments', include('plans_payments.urls')),
        ...
    ]

Set ``django-plans`` settings and set model to:

.. code-block:: python

   PAYMENT_MODEL = 'plans_payments.Payment'


Features
--------

* TODO

Running Tests
-------------

Does the code actually work?

::

    source <YOURVIRTUALENV>/bin/activate
    (myenv) $ pip install tox
    (myenv) $ tox

Credits
-------

Tools used in rendering this package:

*  Cookiecutter_
*  `cookiecutter-djangopackage`_

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`cookiecutter-djangopackage`: https://github.com/pydanny/cookiecutter-djangopackage
