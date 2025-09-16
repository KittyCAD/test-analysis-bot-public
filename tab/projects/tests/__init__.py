from dataclasses import dataclass


@dataclass
class ExampleTest:
    case: str
    name: str
    regex: str = ""
    substring: str = ""


EXAMPLE_TESTS = [
    ExampleTest(
        case="Generic",
        name="my-test",
        regex=r"my\-test",
        substring="my-test",
    ),
    ExampleTest(
        case="Generic spaces",
        name=" name with extra spaces ",
        regex="name with extra spaces",
        substring="name with extra spaces",
    ),
    ExampleTest(
        case="Generic quotes",
        name='name with "quoted" words',
        regex="name with .quoted. words",
    ),
    ExampleTest(
        case="Generic grouping",
        name="my_suite › my_test",
        regex="my_suite.*my_test",
        substring="my_suite and my_test",
    ),
    ExampleTest(
        case="Playwright",
        name="native-file-menu.spec.ts › Native file menu › Home page",
        regex="Native file menu.*Home page",
    ),
    ExampleTest(
        case="Jest",
        name="jest tests › billing.jesttest.tsx › Shows a loading spinner when uninitialized credit count",
        regex="Shows a loading spinner when uninitialized credit count",
    ),
    ExampleTest(
        case="Vitest",
        name="vitest tests › src/lang/modifyAst/faces.test.ts › Testing addShell > should add a shell call on variable-less extrude",
        regex=r"Testing addShell should add a shell call on variable\-less extrude",
    ),
    ExampleTest(
        case="Cargo Nextest",
        name="nextest-run › kcl-lib › docs::kcl_doc::test::kcl_test_examples_std_helix_0",
        regex="docs::kcl_doc::test::kcl_test_examples_std_helix_0",
    ),
    ExampleTest(
        case="Cargo Nextest",
        name="nextest-run › kcl-lib::executor › kcl_test_exporting_step_file",
        regex="kcl_test_exporting_step_file",
    ),
    ExampleTest(
        case="Pytest",
        name="pytest › app.tests.test_models.describe_test.describe_str › it_formats_name",
        substring="describe_str and it_formats_name",
    ),
]
