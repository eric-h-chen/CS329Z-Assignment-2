"""Daily settlement report pipeline.

The package reads a processor's event export together with the merchant
directory and a table of foreign-exchange rates, and produces a per-merchant,
per-day settlement report plus a list of rejected transactions.

Run it as a module::

    python -m pipeline.cli --data DATA_DIR --month YYYY-MM --out OUT_DIR
"""

__version__ = "2.4.1"
