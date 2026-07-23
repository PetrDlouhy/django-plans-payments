.. :changelog:

History
-------

Unreleased
++++++++++
* Add the wallet interface to ``RecurringUserPlan``: it now provides the
  django-payments ``BaseWallet`` fields (``status``, JSON ``extra_data``)
  via migration, and ``payment_completed()`` transitions the wallet on
  payment results (CONFIRMED activates and verifies the token,
  REJECTED/ERROR mark the wallet errored). Requires a django-payments
  build with the wallet interface (not yet in a PyPI release).
* Extract Stripe transaction fees from payment ``attrs``.
* add ``Payment.invalidate_renew_token()`` - payment providers call it when
  the gateway reports the stored recurring token as permanently dead (e.g.
  PayU ``INVALID_TOKEN``). The token is marked unverified so renewal tasks
  stop selecting the account and ``get_renew_token()`` returns ``None``;
  the new ``plans_payments.signals.renew_token_invalidated`` signal lets
  host apps prompt the user to update their payment method.

2.1.0 (2026-07-21)
++++++++++++++++++

* Don't disable ``token_verified`` on an unsuccessful renewal attempt, so a
  transient payment failure no longer permanently disarms automatic renewals
* Add ``get_renew_data()`` and pass provider metadata (e.g. Stripe
  ``customer_id``) through ``set_renew_token(**kwargs)``
* Add migration for the new django-payments ``PaymentStatus.CANCELLED``
  (choices-only, database no-op)
* Tests: drop the unused ``pytz`` dependency, satisfy current black

2.0.2 (2025-05-29)
++++++++++++++++++

* fix the release

2.0.1 (2025-05-29)
++++++++++++++++++

* fix the release

2.0.0 (2025-05-29)
++++++++++++++++++

* Implement the wallet logic
* Drop support for Python 3.8, Django 4.1
* Add support for Django 5.2
* don't obscure Exceptions by catching them

1.5.0 (2025-02-28)
++++++++++++++++++

* Drop support for Python 3.7
* Add support for Python 3.13, Django 5.1
* fix the wrong assumption that ``Payment.extra_data["response"]`` contains a ``"transactions"`` key

1.4.1 (2024-04-24)
++++++++++++++++++

* do not check whether a confirmed payment of a completed order is left anymore

1.4.0 (2024-04-15)
++++++++++++++++++

* migrate to ``RecurringUserPlan.renewal_triggered_by``
* add ``renewal_triggered_by`` parameter to ``Payment.set_renew_token``
* deprecate ``automatic_renewal`` parameter of ``Payment.set_renew_token``; use ``renewal_triggered_by`` parameter instead
* deprecate ``None`` value of ``renewal_triggered_by`` parameter of ``Payment.set_renew_token``; set an ``AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY`` instead

1.3.1 (2024-04-15)
++++++++++++++++++

* fix typo in payment description

1.3.0 (2024-04-12)
++++++++++++++++++

* add optional returning orders when payments are refunded

1.2.2 (2023-12-20)
++++++++++++++++++

* add change_reason for django-simple-history

1.2.1 (2023-12-19)
++++++++++++++++++

* specify sender=Payment for change_payment_status receiver

1.2.0 (2023-10-16)
++++++++++++++++++

* bugfix release (fix prevoius bad release)

1.1.3 (2023-10-15)
++++++++++++++++++

* add some indexes to Payment model

1.1.2 (2023-03-29)
++++++++++++++++++

* reword Payment description to ommit word "Subscribtion" which might raise warnings for banks/card providers

1.1.1 (2023-01-27)
++++++++++++++++++

* correction release, include wheel update, correctly rebase to master

1.1.0 (2023-01-27)
++++++++++++++++++

* Fix transaction fee double counting

1.0.1 (2022-12-09)
++++++++++++++++++

* Fix migrations

1.0.0 (2022-12-08)
++++++++++++++++++

* Recurring payments functionality

0.2.0 (2018-08-05)
++++++++++++++++++

* Payment process without capturing should work
* Automatic buttons generation

0.1.0 (2018-07-23)
++++++++++++++++++

* First release on PyPI.
