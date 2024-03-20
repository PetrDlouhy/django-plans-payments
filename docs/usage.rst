=====
Usage
=====

To use Django plans payments in a project, add it to your `INSTALLED_APPS`:

.. code-block:: python

    INSTALLED_APPS = (
        ...
        'plans_payments.apps.PlansPaymentsConfig',
        ...
    )

Add Django plans payments's URL patterns:

.. code-block:: python

    from plans_payments import urls as plans_payments_urls


    urlpatterns = [
        ...
        url(r'^', include(plans_payments_urls)),
        ...
    ]

To enable returning orders when payments are refunded, set `PLANS_PAYMENTS_RETURN_ORDER_WHEN_PAYMENT_REFUNDED` to `True` in your settings.

.. code-block:: python

    PLANS_PAYMENTS_RETURN_ORDER_WHEN_PAYMENT_REFUNDED = True
