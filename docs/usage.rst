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

To complete orders only after the confirmed payment has been committed, set `PLANS_PAYMENTS_COMPLETE_ORDER_AFTER_COMMIT` to `True`.

.. code-block:: python

    PLANS_PAYMENTS_COMPLETE_ORDER_AFTER_COMMIT = True

By default the order is completed inside the transaction that confirms the payment, so a failure while completing it (for example a lock timeout while numbering the invoice) rolls back the payment's confirmation too. For a provider that has already captured the money, such as a PayPal checkout, that leaves the buyer charged with no confirmed payment on record. With this setting the confirmed payment commits first and the order is completed right after. If completion fails, the payment stays confirmed, the exception still propagates, and the provider's next confirmation (a notification retry) completes the order.
