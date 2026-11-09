# Frozen 50-Task Benchmark Manifest: Gemma 4 E4B Small Model Track

Curated from human-verified genuine repository issues (SWE-bench Verified & Lite).
Partitioned into 25 Development tasks and 25 strictly Held-Out tasks.

## 1. Summary by Repository

| Repository | License | Dev Tasks | Held-Out Tasks | Total Tasks |
| :--- | :--- | :--- | :--- | :--- |
| `pallets/flask` | BSD-3-Clause | 2 | 2 | 4 |
| `psf/requests` | Apache-2.0 | 3 | 3 | 6 |
| `pytest-dev/pytest` | MIT | 4 | 4 | 8 |
| `sympy/sympy` | BSD-3-Clause | 5 | 5 | 10 |
| `django/django` | BSD-3-Clause | 6 | 6 | 12 |
| `scikit-learn/scikit-learn` | BSD-3-Clause | 2 | 2 | 4 |
| `matplotlib/matplotlib` | PSF / BSD-compatible | 1 | 1 | 2 |
| `pydata/xarray` | Apache-2.0 | 1 | 1 | 2 |
| `pylint-dev/pylint` | GPL-2.0-or-later | 1 | 1 | 2 |
| **TOTAL** | - | **25** | **25** | **50** |

## 2. Complete Task Registry

| # | Instance ID | Repository | Split | Base Commit | Target Files | F2P Count |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `pallets__flask-4045` | `pallets/flask` | **dev** | `d8c37f4372` | `src/flask/blueprints.py` | 2 |
| 2 | `pallets__flask-4992` | `pallets/flask` | **dev** | `4c288bc97e` | `src/flask/config.py` | 1 |
| 3 | `psf__requests-1963` | `psf/requests` | **dev** | `110048f983` | `requests/sessions.py` | 7 |
| 4 | `psf__requests-2148` | `psf/requests` | **dev** | `fe693c4922` | `requests/models.py` | 10 |
| 5 | `psf__requests-2317` | `psf/requests` | **dev** | `091991be0d` | `requests/sessions.py` | 8 |
| 6 | `pytest-dev__pytest-11143` | `pytest-dev/pytest` | **dev** | `6995257cf4` | `src/_pytest/assertion/rewrite.py` | 1 |
| 7 | `pytest-dev__pytest-11148` | `pytest-dev/pytest` | **dev** | `2f7415cfbc` | `src/_pytest/pathlib.py` | 2 |
| 8 | `pytest-dev__pytest-5103` | `pytest-dev/pytest` | **dev** | `10ca84ffc5` | `src/_pytest/assertion/rewrite.py` | 1 |
| 9 | `pytest-dev__pytest-5221` | `pytest-dev/pytest` | **dev** | `4a2fdce62b` | `src/_pytest/python.py` | 2 |
| 10 | `sympy__sympy-11400` | `sympy/sympy` | **dev** | `8dcb12a6cf` | `sympy/printing/ccode.py` | 2 |
| 11 | `sympy__sympy-11870` | `sympy/sympy` | **dev** | `5c2e1f96a7` | `sympy/functions/elementary/trigonometric.py` | 1 |
| 12 | `sympy__sympy-11897` | `sympy/sympy` | **dev** | `e2918c1205` | `sympy/printing/latex.py` | 1 |
| 13 | `sympy__sympy-12171` | `sympy/sympy` | **dev** | `ca6ef27272` | `sympy/printing/mathematica.py` | 1 |
| 14 | `sympy__sympy-12236` | `sympy/sympy` | **dev** | `d60497958f` | `sympy/polys/domains/polynomialring.py` | 1 |
| 15 | `django__django-10914` | `django/django` | **dev** | `e7fd69d051` | `django/conf/global_settings.py` | 1 |
| 16 | `django__django-10924` | `django/django` | **dev** | `bceadd2788` | `django/db/models/fields/__init__.py` | 1 |
| 17 | `django__django-11001` | `django/django` | **dev** | `ef082ebb84` | `django/db/models/sql/compiler.py` | 2 |
| 18 | `django__django-11019` | `django/django` | **dev** | `93e892bb64` | `django/forms/widgets.py` | 16 |
| 19 | `django__django-11039` | `django/django` | **dev** | `d527639804` | `django/core/management/commands/sqlmigrate.py` | 1 |
| 20 | `django__django-11049` | `django/django` | **dev** | `17455e924e` | `django/db/models/fields/__init__.py` | 1 |
| 21 | `scikit-learn__scikit-learn-10297` | `scikit-learn/scikit-learn` | **dev** | `b90661d6a4` | `sklearn/linear_model/ridge.py` | 1 |
| 22 | `scikit-learn__scikit-learn-10508` | `scikit-learn/scikit-learn` | **dev** | `c753b77ac4` | `sklearn/preprocessing/label.py` | 2 |
| 23 | `matplotlib__matplotlib-18869` | `matplotlib/matplotlib` | **dev** | `b7d0591986` | `lib/matplotlib/__init__.py` | 4 |
| 24 | `pydata__xarray-3364` | `pydata/xarray` | **dev** | `863e49066c` | `xarray/core/concat.py` | 2 |
| 25 | `pylint-dev__pylint-5859` | `pylint-dev/pylint` | **dev** | `182cc539b8` | `pylint/checkers/misc.py` | 1 |
| 26 | `pallets__flask-5063` | `pallets/flask` | **heldout** | `182ce3dd15` | `src/flask/cli.py` | 2 |
| 27 | `pallets__flask-5014` | `pallets/flask` | **heldout** | `7ee9ceb71e` | `src/flask/blueprints.py` | 1 |
| 28 | `psf__requests-2674` | `psf/requests` | **heldout** | `0be38a0c37` | `requests/adapters.py` | 12 |
| 29 | `psf__requests-3362` | `psf/requests` | **heldout** | `36453b95b1` | `requests/utils.py` | 1 |
| 30 | `psf__requests-863` | `psf/requests` | **heldout** | `a0df2cbb10` | `requests/models.py` | 4 |
| 31 | `pytest-dev__pytest-5227` | `pytest-dev/pytest` | **heldout** | `2051e30b9b` | `src/_pytest/logging.py` | 3 |
| 32 | `pytest-dev__pytest-5413` | `pytest-dev/pytest` | **heldout** | `450d264623` | `src/_pytest/_code/code.py` | 1 |
| 33 | `pytest-dev__pytest-5495` | `pytest-dev/pytest` | **heldout** | `1aefb24b37` | `src/_pytest/assertion/util.py` | 2 |
| 34 | `pytest-dev__pytest-5692` | `pytest-dev/pytest` | **heldout** | `29e336bd9b` | `src/_pytest/junitxml.py` | 2 |
| 35 | `sympy__sympy-12419` | `sympy/sympy` | **heldout** | `479939f8c6` | `sympy/matrices/expressions/matexpr.py` | 1 |
| 36 | `sympy__sympy-12454` | `sympy/sympy` | **heldout** | `d3fcdb72bf` | `sympy/matrices/matrices.py` | 2 |
| 37 | `sympy__sympy-12481` | `sympy/sympy` | **heldout** | `c807dfe756` | `sympy/combinatorics/permutations.py` | 1 |
| 38 | `sympy__sympy-13031` | `sympy/sympy` | **heldout** | `2dfa7457f2` | `sympy/matrices/sparse.py` | 1 |
| 39 | `sympy__sympy-13043` | `sympy/sympy` | **heldout** | `a3389a25ec` | `sympy/integrals/intpoly.py` | 1 |
| 40 | `django__django-11099` | `django/django` | **heldout** | `d26b242443` | `django/contrib/auth/validators.py` | 3 |
| 41 | `django__django-11133` | `django/django` | **heldout** | `879cc3da62` | `django/http/response.py` | 1 |
| 42 | `django__django-11179` | `django/django` | **heldout** | `19fc6376ce` | `django/db/models/deletion.py` | 1 |
| 43 | `django__django-11283` | `django/django` | **heldout** | `08a4ee0651` | `django/contrib/auth/migrations/0011_update_proxy_permissions.py` | 1 |
| 44 | `django__django-11422` | `django/django` | **heldout** | `df46b329e0` | `django/utils/autoreload.py` | 1 |
| 45 | `django__django-11564` | `django/django` | **heldout** | `580e644f24` | `django/conf/__init__.py` | 2 |
| 46 | `scikit-learn__scikit-learn-10949` | `scikit-learn/scikit-learn` | **heldout** | `3b5abf7659` | `sklearn/utils/validation.py` | 1 |
| 47 | `scikit-learn__scikit-learn-11040` | `scikit-learn/scikit-learn` | **heldout** | `96a02f3934` | `sklearn/neighbors/base.py` | 1 |
| 48 | `matplotlib__matplotlib-22711` | `matplotlib/matplotlib` | **heldout** | `f670fe7879` | `lib/matplotlib/widgets.py` | 2 |
| 49 | `pydata__xarray-4094` | `pydata/xarray` | **heldout** | `a64cf2d547` | `xarray/core/dataarray.py` | 1 |
| 50 | `pylint-dev__pylint-6506` | `pylint-dev/pylint` | **heldout** | `0a4204fd75` | `pylint/config/config_initialization.py` | 2 |
