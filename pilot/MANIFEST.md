# Frozen Task Manifest: Gemma 4 Developer Agent E2E Pilot (10 Real Python Issues)

Статус: FROZEN_MANIFEST. Выборка из 10 реальных задач из официального SWE-bench Lite (princeton-nlp/SWE-bench_Lite).
Зафиксированы базовые коммиты, хеши test patch, списки FAIL_TO_PASS и PASS_TO_PASS тестов.

## 1. Сводная таблица задач

| Task ID | Repository | Base Commit | F2P Tests | P2P Tests | Test Patch SHA256 (префикс) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `pallets__flask-4045` | `pallets/flask` | `d8c37f4372` | 2 | 50 | `def1da53a3857f67` |
| `pallets__flask-4992` | `pallets/flask` | `4c288bc97e` | 1 | 18 | `851c94393511592a` |
| `pallets__flask-5063` | `pallets/flask` | `182ce3dd15` | 2 | 54 | `e5b1124e11d391cc` |
| `psf__requests-1963` | `psf/requests` | `110048f983` | 7 | 112 | `d54962cb131f871d` |
| `psf__requests-2148` | `psf/requests` | `fe693c4922` | 10 | 118 | `ad6a641480a841a4` |
| `pytest-dev__pytest-5103` | `pytest-dev/pytest` | `10ca84ffc5` | 1 | 64 | `89740f6cb7127fc9` |
| `pytest-dev__pytest-5221` | `pytest-dev/pytest` | `4a2fdce62b` | 2 | 170 | `2ef78e8e8f6ae696` |
| `sympy__sympy-11400` | `sympy/sympy` | `8dcb12a6cf` | 2 | 29 | `e9398bf638c46e8c` |
| `sympy__sympy-11870` | `sympy/sympy` | `5c2e1f96a7` | 1 | 58 | `0a8abafeed218953` |
| `sympy__sympy-12171` | `sympy/sympy` | `ca6ef27272` | 1 | 8 | `4e0dcceec782a7eb` |

## 2. Детальная спецификация задач

### pallets__flask-4045
- **Репозиторий:** https://github.com/pallets/flask
- **Base commit:** `d8c37f43724cd9fb0870f77877b7c4c7e38a19e0`
- **Test patch SHA256:** `def1da53a3857f67b571f108abde6fcdac61da5c7820c0749fa7c487fe87a62a`
- **Gold patch SHA256:** `6c4055e1cb35cf9c5d50bbba639af1787d6f5d5146f9539cedc364a43d01c687`
- **Обязательные FAIL_TO_PASS тесты:**
  * `tests/test_blueprints.py::test_dotted_name_not_allowed`
  * `tests/test_blueprints.py::test_route_decorator_custom_endpoint_with_dots`

### pallets__flask-4992
- **Репозиторий:** https://github.com/pallets/flask
- **Base commit:** `4c288bc97ea371817199908d0d9b12de9dae327e`
- **Test patch SHA256:** `851c94393511592a1e3b65ea1d909b73b342ef55388819c6bd9632edb71ad304`
- **Gold patch SHA256:** `db912cc1331807c9b0715766eb45a5fac8c4036a99dd54c9ce998b675d0d8697`
- **Обязательные FAIL_TO_PASS тесты:**
  * `tests/test_config.py::test_config_from_file_toml`

### pallets__flask-5063
- **Репозиторий:** https://github.com/pallets/flask
- **Base commit:** `182ce3dd15dfa3537391c3efaf9c3ff407d134d4`
- **Test patch SHA256:** `e5b1124e11d391cc01f7d9d03ada6ccd629a817a3334d5980884ed276237bf96`
- **Gold patch SHA256:** `f9c1ef426acac91e34d551f80f34dfe27fc124ac316af71d70eec1764b4a6497`
- **Обязательные FAIL_TO_PASS тесты:**
  * `tests/test_cli.py::TestRoutes::test_subdomain`
  * `tests/test_cli.py::TestRoutes::test_host`

### psf__requests-1963
- **Репозиторий:** https://github.com/psf/requests
- **Base commit:** `110048f9837f8441ea536804115e80b69f400277`
- **Test patch SHA256:** `d54962cb131f871dcfb26c9d5b4518da0c701fd998915837bec0b3d80d9492a0`
- **Gold patch SHA256:** `deb8b9018ea0271b2b9dc2d883bf5fb0ca9a721ecc9a93718065926fbec4ed74`
- **Обязательные FAIL_TO_PASS тесты:**
  * `test_requests.py::RequestsTestCase::test_DIGESTAUTH_QUOTES_QOP_VALUE`
  * `test_requests.py::RequestsTestCase::test_DIGESTAUTH_WRONG_HTTP_401_GET`
  * `test_requests.py::RequestsTestCase::test_DIGEST_AUTH_RETURNS_COOKIE`
  * `test_requests.py::RequestsTestCase::test_DIGEST_HTTP_200_OK_GET`
  * `test_requests.py::RequestsTestCase::test_POSTBIN_GET_POST_FILES_WITH_DATA`
  * `test_requests.py::RequestsTestCase::test_param_cookiejar_works`
  * `test_requests.py::TestRedirects::test_requests_are_updated_each_time`

### psf__requests-2148
- **Репозиторий:** https://github.com/psf/requests
- **Base commit:** `fe693c492242ae532211e0c173324f09ca8cf227`
- **Test patch SHA256:** `ad6a641480a841a4e54349518842cde8e7562813178057e5cd8b44e9e8af8e27`
- **Gold patch SHA256:** `0c773284a62e168b99a78a22c778e4366861e5dac37e7ffb4ae85a680843fab5`
- **Обязательные FAIL_TO_PASS тесты:**
  * `test_requests.py::RequestsTestCase::test_DIGEST_AUTH_RETURNS_COOKIE`
  * `test_requests.py::RequestsTestCase::test_HTTP_200_OK_GET_ALTERNATIVE`
  * `test_requests.py::RequestsTestCase::test_HTTP_200_OK_HEAD`
  * `test_requests.py::RequestsTestCase::test_POSTBIN_GET_POST_FILES`
  * `test_requests.py::RequestsTestCase::test_auth_is_stripped_on_redirect_off_host`
  * `test_requests.py::RequestsTestCase::test_basicauth_with_netrc`
  * `test_requests.py::RequestsTestCase::test_cookie_quote_wrapped`
  * `test_requests.py::RequestsTestCase::test_generic_cookiejar_works`
  * `test_requests.py::RequestsTestCase::test_iter_content_handles_socket_error`
  * `test_requests.py::RequestsTestCase::test_unicode_multipart_post`

### pytest-dev__pytest-5103
- **Репозиторий:** https://github.com/pytest-dev/pytest
- **Base commit:** `10ca84ffc56c2dd2d9dc4bd71b7b898e083500cd`
- **Test patch SHA256:** `89740f6cb7127fc954eb9fa2a84e7b6df26e77f18b76bf96b50db5bfb0ba5c86`
- **Gold patch SHA256:** `5b621eb0099e1e4eeb2bcb42f24a48b15b540e46fe23403475890578f546680c`
- **Обязательные FAIL_TO_PASS тесты:**
  * `testing/test_assertrewrite.py::TestAssertionRewrite::test_unroll_expression`

### pytest-dev__pytest-5221
- **Репозиторий:** https://github.com/pytest-dev/pytest
- **Base commit:** `4a2fdce62b73944030cff9b3e52862868ca9584d`
- **Test patch SHA256:** `2ef78e8e8f6ae6965c52756f15af115a80e980bcb52dfe7147a7d38c6f70de08`
- **Gold patch SHA256:** `be5549ceff2ee5643ad3743e8919241e16ebf9549c79c68cd56a0ee3aaaf666b`
- **Обязательные FAIL_TO_PASS тесты:**
  * `testing/python/fixtures.py::TestShowFixtures::test_show_fixtures`
  * `testing/python/fixtures.py::TestShowFixtures::test_show_fixtures_verbose`

### sympy__sympy-11400
- **Репозиторий:** https://github.com/sympy/sympy
- **Base commit:** `8dcb12a6cf500e8738d6729ab954a261758f49ca`
- **Test patch SHA256:** `e9398bf638c46e8c411f2eb3e8f096b92c4638ba896ac68d120fe810b7b1b0f4`
- **Gold patch SHA256:** `7f79e0c6e6909a311c54215f3e858f057db77bb11248853e84095261195d6c1b`
- **Обязательные FAIL_TO_PASS тесты:**
  * `test_ccode_Relational`
  * `test_ccode_sinc`

### sympy__sympy-11870
- **Репозиторий:** https://github.com/sympy/sympy
- **Base commit:** `5c2e1f96a7ff562d4a778f4ca9ffc9c81557197e`
- **Test patch SHA256:** `0a8abafeed218953c8a64ccba38c0f9ff027e7b372f0176e8a43d0a208fa84f1`
- **Gold patch SHA256:** `051c56fee9628243fb9c8fdcaae677f7cd82afcf8574e373b87dda95b11b57df`
- **Обязательные FAIL_TO_PASS тесты:**
  * `test_sinc`

### sympy__sympy-12171
- **Репозиторий:** https://github.com/sympy/sympy
- **Base commit:** `ca6ef27272be31c9dc3753ede9232c39df9a75d8`
- **Test patch SHA256:** `4e0dcceec782a7eb6996e6102808f989593578825a2cb057d00a8b97f179e251`
- **Gold patch SHA256:** `44ff6d656d8ce81cf1010326235df148a0146a8e736aad4186d597e272f66243`
- **Обязательные FAIL_TO_PASS тесты:**
  * `test_Derivative`

