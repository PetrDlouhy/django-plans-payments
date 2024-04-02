.. :changelog:

History
-------

1.4.0 (Unreleased)
++++++++++++++++++

* migrate to `RecurringUserPlan.renewal_triggered_by`
* add `renewal_triggered_by` parameter to `Payment.set_renew_token`
* deprecate `automatic_renewal` parameter of `Payment.set_renew_token`; use `renewal_triggered_by` parameter instead
* deprecate `None` value of `renewal_triggered_by` parameter of `Payment.set_renew_token`; set an `AbstractRecurringUserPlan.RENEWAL_TRIGGERED_BY` instead

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
