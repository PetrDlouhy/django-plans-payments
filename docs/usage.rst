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
