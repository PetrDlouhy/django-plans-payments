=============================
Django plans payments
=============================

.. image:: https://badge.fury.io/py/django-plans-payments.svg
    :target: https://badge.fury.io/py/django-plans-payments

.. image:: https://github.com/PetrDlouhy/django-plans-payments/actions/workflows/main.yml/badge.svg
    :target: https://github.com/PetrDlouhy/django-plans-payments/actions/workflows/main.yml

.. image:: https://codecov.io/gh/PetrDlouhy/django-plans-payments/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/PetrDlouhy/django-plans-payments

Almost automatic integration between `django-plans <https://github.com/django-getpaid/django-plans>`_ and `django-payments <https://github.com/mirumee/django-payments>`_.
This will add payment buttons to the order page and automatically confirm the `Order` after the payment. Optionally, it can return the corresponding order when a payment is refunded.

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
        'related_admin',
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

Customer IP address
-------------------

Customer IP address is stored in Payment model and used for some payment providers (i.e. PayU).
For security reasons `django-plans-payments` does acquire the IP only from ``request`` ``REMOTE_ADDR`` parameter.
If you are behind proxy, you will need to setup some mechanism to populate this variable from ``HTTP_X_FORWARDED_FOR`` parameter.
The suggested solution is to use `django-httpforwardedfor <https://github.com/PaesslerAG/django-httpxforwardedfor>`_ or `django-xff <https://github.com/ferrix/xff/>`_ application for that.

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
