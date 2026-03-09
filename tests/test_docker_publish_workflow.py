"""
Comprehensive tests for the Docker publish GitHub Actions workflow.

This test suite validates the .github/workflows/docker-publish.yml file to ensure:
- YAML syntax is valid
- Workflow structure is correct
- All required steps are present
- Action versions are specified
- Security configurations are proper
- Cache configuration is optimal
"""

import os
import pytest
import yaml
from pathlib import Path


@pytest.fixture
def workflow_file_path():
    """Return the path to the docker-publish workflow file."""
    repo_root = Path(__file__).parent.parent
    return repo_root / ".github" / "workflows" / "docker-publish.yml"


@pytest.fixture
def workflow_content(workflow_file_path):
    """
    Load and parse the workflow YAML file.

    Note: PyYAML converts the 'on' key to boolean True because 'on' is a YAML boolean value.
    This is standard YAML 1.1 behavior. Tests should access triggers using True instead of 'on'.
    """
    with open(workflow_file_path, "r") as f:
        return yaml.safe_load(f)


def get_workflow_triggers(workflow_content):
    """
    Helper function to get workflow triggers.

    PyYAML converts 'on:' to True (boolean), so we need to access it using True.
    This is standard YAML 1.1 behavior where 'on', 'yes', 'true' are booleans.
    """
    # The 'on' key in YAML is converted to boolean True by PyYAML
    return workflow_content.get(True) or workflow_content.get("on")


class TestWorkflowFileExists:
    """Test that the workflow file exists and is readable."""

    def test_workflow_file_exists(self, workflow_file_path):
        """Verify the workflow file exists."""
        assert workflow_file_path.exists(), f"Workflow file not found at {workflow_file_path}"

    def test_workflow_file_readable(self, workflow_file_path):
        """Verify the workflow file is readable."""
        assert os.access(workflow_file_path, os.R_OK), "Workflow file is not readable"


class TestWorkflowYAMLValidity:
    """Test YAML syntax and structure."""

    def test_yaml_is_valid(self, workflow_file_path):
        """Verify the workflow file contains valid YAML."""
        with open(workflow_file_path, "r") as f:
            content = yaml.safe_load(f)
        assert content is not None, "YAML file is empty or invalid"

    def test_yaml_is_dict(self, workflow_content):
        """Verify the workflow content is a dictionary."""
        assert isinstance(workflow_content, dict), "Workflow content must be a dictionary"


class TestWorkflowMetadata:
    """Test workflow name and basic metadata."""

    def test_workflow_has_name(self, workflow_content):
        """Verify the workflow has a name."""
        assert "name" in workflow_content, "Workflow must have a 'name' field"

    def test_workflow_name_is_descriptive(self, workflow_content):
        """Verify the workflow name is descriptive and not empty."""
        name = workflow_content.get("name", "")
        assert len(name) > 0, "Workflow name cannot be empty"
        assert "docker" in name.lower(), "Workflow name should reference Docker"

    def test_workflow_name_matches_expected(self, workflow_content):
        """Verify the workflow has the expected name."""
        assert workflow_content["name"] == "Build & Publish Docker Image"


class TestWorkflowTriggers:
    """Test workflow trigger configuration."""

    def test_workflow_has_triggers(self, workflow_content):
        """Verify the workflow has trigger configuration."""
        triggers = get_workflow_triggers(workflow_content)
        assert triggers is not None, "Workflow must have trigger configuration"

    def test_workflow_triggers_on_push(self, workflow_content):
        """Verify the workflow triggers on push events."""
        triggers = get_workflow_triggers(workflow_content)
        assert "push" in triggers, "Workflow should trigger on push events"

    def test_workflow_push_trigger_has_branches(self, workflow_content):
        """Verify push trigger specifies branches."""
        triggers = get_workflow_triggers(workflow_content)
        push_config = triggers["push"]
        assert "branches" in push_config, "Push trigger should specify branches"

    def test_workflow_triggers_on_main_branch(self, workflow_content):
        """Verify the workflow triggers on main branch."""
        triggers = get_workflow_triggers(workflow_content)
        branches = triggers["push"]["branches"]
        assert "main" in branches, "Workflow should trigger on main branch"

    def test_workflow_only_triggers_on_main(self, workflow_content):
        """Verify the workflow only triggers on main branch (no other branches)."""
        triggers = get_workflow_triggers(workflow_content)
        branches = triggers["push"]["branches"]
        assert branches == ["main"], "Workflow should only trigger on main branch"


class TestWorkflowJobs:
    """Test job definitions in the workflow."""

    def test_workflow_has_jobs(self, workflow_content):
        """Verify the workflow has jobs defined."""
        assert "jobs" in workflow_content, "Workflow must have jobs"

    def test_workflow_has_build_and_push_job(self, workflow_content):
        """Verify the workflow has a build-and-push job."""
        jobs = workflow_content["jobs"]
        assert "build-and-push" in jobs, "Workflow should have 'build-and-push' job"

    def test_job_runs_on_ubuntu(self, workflow_content):
        """Verify the job runs on ubuntu-latest."""
        job = workflow_content["jobs"]["build-and-push"]
        assert "runs-on" in job, "Job must specify runs-on"
        assert job["runs-on"] == "ubuntu-latest", "Job should run on ubuntu-latest"


class TestJobPermissions:
    """Test job permission configuration."""

    def test_job_has_permissions(self, workflow_content):
        """Verify the job has permissions defined."""
        job = workflow_content["jobs"]["build-and-push"]
        assert "permissions" in job, "Job should have permissions defined"

    def test_job_has_read_contents_permission(self, workflow_content):
        """Verify the job has contents read permission."""
        permissions = workflow_content["jobs"]["build-and-push"]["permissions"]
        assert "contents" in permissions, "Job should have contents permission"
        assert permissions["contents"] == "read", "Contents permission should be 'read'"

    def test_job_has_write_packages_permission(self, workflow_content):
        """Verify the job has packages write permission."""
        permissions = workflow_content["jobs"]["build-and-push"]["permissions"]
        assert "packages" in permissions, "Job should have packages permission"
        assert permissions["packages"] == "write", "Packages permission should be 'write'"

    def test_permissions_follow_least_privilege(self, workflow_content):
        """Verify permissions follow principle of least privilege."""
        permissions = workflow_content["jobs"]["build-and-push"]["permissions"]
        # Should only have necessary permissions
        assert len(permissions) == 2, "Should only have necessary permissions"
        assert permissions["contents"] == "read", "Contents should be read-only"
        assert permissions["packages"] == "write", "Packages needs write for publishing"


class TestJobSteps:
    """Test the steps in the build-and-push job."""

    def test_job_has_steps(self, workflow_content):
        """Verify the job has steps defined."""
        job = workflow_content["jobs"]["build-and-push"]
        assert "steps" in job, "Job must have steps"

    def test_job_has_multiple_steps(self, workflow_content):
        """Verify the job has multiple steps."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        assert len(steps) >= 5, "Job should have at least 5 steps"

    def test_step_count_matches_expected(self, workflow_content):
        """Verify the exact number of steps."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        assert len(steps) == 5, "Job should have exactly 5 steps"


class TestCheckoutStep:
    """Test the checkout step."""

    def test_checkout_step_exists(self, workflow_content):
        """Verify the checkout step exists."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        assert any("checkout" in step.get("uses", "") for step in steps), \
            "Should have checkout step"

    def test_checkout_step_is_first(self, workflow_content):
        """Verify the checkout step is the first step."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        first_step = steps[0]
        assert "uses" in first_step, "First step should use an action"
        assert "checkout" in first_step["uses"], "First step should be checkout"

    def test_checkout_uses_v4(self, workflow_content):
        """Verify checkout action uses v4."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        checkout_step = steps[0]
        assert checkout_step["uses"] == "actions/checkout@v4", \
            "Should use actions/checkout@v4"


class TestBuildxSetupStep:
    """Test the Docker Buildx setup step."""

    def test_buildx_setup_exists(self, workflow_content):
        """Verify the buildx setup step exists."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        assert any("setup-buildx-action" in step.get("uses", "") for step in steps), \
            "Should have buildx setup step"

    def test_buildx_setup_is_second_step(self, workflow_content):
        """Verify the buildx setup is the second step."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        second_step = steps[1]
        assert "setup-buildx-action" in second_step.get("uses", ""), \
            "Second step should be buildx setup"

    def test_buildx_uses_v3(self, workflow_content):
        """Verify buildx setup uses v3."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        buildx_step = steps[1]
        assert buildx_step["uses"] == "docker/setup-buildx-action@v3", \
            "Should use docker/setup-buildx-action@v3"


class TestDockerLoginStep:
    """Test the Docker login step."""

    def test_docker_login_exists(self, workflow_content):
        """Verify the Docker login step exists."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        assert any("login-action" in step.get("uses", "") for step in steps), \
            "Should have Docker login step"

    def test_docker_login_is_third_step(self, workflow_content):
        """Verify the Docker login is the third step."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        third_step = steps[2]
        assert "login-action" in third_step.get("uses", ""), \
            "Third step should be Docker login"

    def test_docker_login_uses_v3(self, workflow_content):
        """Verify Docker login uses v3."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        login_step = steps[2]
        assert login_step["uses"] == "docker/login-action@v3", \
            "Should use docker/login-action@v3"

    def test_docker_login_has_with_clause(self, workflow_content):
        """Verify Docker login has configuration."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        login_step = steps[2]
        assert "with" in login_step, "Login step should have 'with' configuration"

    def test_docker_login_uses_ghcr(self, workflow_content):
        """Verify Docker login uses GitHub Container Registry."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        login_step = steps[2]
        registry = login_step["with"]["registry"]
        assert registry == "ghcr.io", "Should use ghcr.io registry"

    def test_docker_login_uses_github_actor(self, workflow_content):
        """Verify Docker login uses github.actor for username."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        login_step = steps[2]
        username = login_step["with"]["username"]
        assert username == "${{ github.actor }}", \
            "Should use github.actor for username"

    def test_docker_login_uses_github_token(self, workflow_content):
        """Verify Docker login uses GITHUB_TOKEN secret."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        login_step = steps[2]
        password = login_step["with"]["password"]
        assert password == "${{ secrets.GITHUB_TOKEN }}", \
            "Should use GITHUB_TOKEN secret for password"


class TestMetadataStep:
    """Test the Docker metadata action step."""

    def test_metadata_action_exists(self, workflow_content):
        """Verify the metadata action step exists."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        assert any("metadata-action" in step.get("uses", "") for step in steps), \
            "Should have metadata action step"

    def test_metadata_is_fourth_step(self, workflow_content):
        """Verify the metadata action is the fourth step."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        fourth_step = steps[3]
        assert "metadata-action" in fourth_step.get("uses", ""), \
            "Fourth step should be metadata action"

    def test_metadata_uses_v5(self, workflow_content):
        """Verify metadata action uses v5."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        metadata_step = steps[3]
        assert metadata_step["uses"] == "docker/metadata-action@v5", \
            "Should use docker/metadata-action@v5"

    def test_metadata_has_id(self, workflow_content):
        """Verify metadata step has an id."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        metadata_step = steps[3]
        assert "id" in metadata_step, "Metadata step should have an id"
        assert metadata_step["id"] == "meta", "Metadata step id should be 'meta'"

    def test_metadata_has_with_clause(self, workflow_content):
        """Verify metadata step has configuration."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        metadata_step = steps[3]
        assert "with" in metadata_step, "Metadata step should have 'with' configuration"

    def test_metadata_specifies_images(self, workflow_content):
        """Verify metadata step specifies image name."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        metadata_step = steps[3]
        assert "images" in metadata_step["with"], \
            "Metadata step should specify images"

    def test_metadata_uses_ghcr_with_repository(self, workflow_content):
        """Verify metadata uses ghcr.io with repository."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        metadata_step = steps[3]
        images = metadata_step["with"]["images"]
        assert "ghcr.io/" in images, "Image should use ghcr.io registry"
        assert "${{ github.repository }}" in images, \
            "Image should use github.repository"

    def test_metadata_specifies_tags(self, workflow_content):
        """Verify metadata step specifies tag configuration."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        metadata_step = steps[3]
        assert "tags" in metadata_step["with"], \
            "Metadata step should specify tags"

    def test_metadata_tags_include_latest(self, workflow_content):
        """Verify metadata tags include latest tag."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        metadata_step = steps[3]
        tags = metadata_step["with"]["tags"]
        assert "type=raw,value=latest" in tags, \
            "Tags should include 'type=raw,value=latest'"

    def test_metadata_tags_include_sha(self, workflow_content):
        """Verify metadata tags include SHA tag."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        metadata_step = steps[3]
        tags = metadata_step["with"]["tags"]
        assert "type=sha" in tags, "Tags should include SHA type"
        assert "prefix=sha-" in tags, "SHA tag should have 'sha-' prefix"
        assert "format=short" in tags, "SHA tag should use short format"


class TestBuildPushStep:
    """Test the Docker build and push step."""

    def test_build_push_action_exists(self, workflow_content):
        """Verify the build and push action step exists."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        assert any("build-push-action" in step.get("uses", "") for step in steps), \
            "Should have build and push action step"

    def test_build_push_is_fifth_step(self, workflow_content):
        """Verify the build and push action is the fifth step."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        fifth_step = steps[4]
        assert "build-push-action" in fifth_step.get("uses", ""), \
            "Fifth step should be build and push action"

    def test_build_push_uses_v5(self, workflow_content):
        """Verify build and push action uses v5."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        build_step = steps[4]
        assert build_step["uses"] == "docker/build-push-action@v5", \
            "Should use docker/build-push-action@v5"

    def test_build_push_has_with_clause(self, workflow_content):
        """Verify build and push step has configuration."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        build_step = steps[4]
        assert "with" in build_step, "Build step should have 'with' configuration"

    def test_build_push_specifies_context(self, workflow_content):
        """Verify build step specifies build context."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        build_step = steps[4]
        assert "context" in build_step["with"], "Build step should specify context"
        assert build_step["with"]["context"] == ".", \
            "Build context should be current directory"

    def test_build_push_enabled(self, workflow_content):
        """Verify push is enabled in build step."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        build_step = steps[4]
        assert "push" in build_step["with"], "Build step should specify push"
        assert build_step["with"]["push"] is True, "Push should be enabled"

    def test_build_push_uses_meta_tags(self, workflow_content):
        """Verify build step uses tags from metadata step."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        build_step = steps[4]
        assert "tags" in build_step["with"], "Build step should specify tags"
        tags = build_step["with"]["tags"]
        assert "${{ steps.meta.outputs.tags }}" == tags, \
            "Should use tags from meta step"

    def test_build_push_uses_meta_labels(self, workflow_content):
        """Verify build step uses labels from metadata step."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        build_step = steps[4]
        assert "labels" in build_step["with"], "Build step should specify labels"
        labels = build_step["with"]["labels"]
        assert "${{ steps.meta.outputs.labels }}" == labels, \
            "Should use labels from meta step"


class TestCacheConfiguration:
    """Test Docker build cache configuration."""

    def test_build_has_cache_from(self, workflow_content):
        """Verify build step configures cache-from."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        build_step = steps[4]
        assert "cache-from" in build_step["with"], \
            "Build step should configure cache-from"

    def test_cache_from_uses_gha(self, workflow_content):
        """Verify cache-from uses GitHub Actions cache."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        build_step = steps[4]
        cache_from = build_step["with"]["cache-from"]
        assert cache_from == "type=gha", \
            "cache-from should use GitHub Actions cache (type=gha)"

    def test_build_has_cache_to(self, workflow_content):
        """Verify build step configures cache-to."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        build_step = steps[4]
        assert "cache-to" in build_step["with"], \
            "Build step should configure cache-to"

    def test_cache_to_uses_gha_with_mode_max(self, workflow_content):
        """Verify cache-to uses GitHub Actions cache with mode=max."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        build_step = steps[4]
        cache_to = build_step["with"]["cache-to"]
        assert "type=gha" in cache_to, \
            "cache-to should use GitHub Actions cache (type=gha)"
        assert "mode=max" in cache_to, \
            "cache-to should use mode=max for maximum caching"


class TestSecurityBestPractices:
    """Test security best practices in the workflow."""

    def test_actions_use_specific_versions(self, workflow_content):
        """Verify all actions use specific version tags (not 'latest')."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        for step in steps:
            if "uses" in step:
                action = step["uses"]
                assert "@" in action, f"Action {action} should specify a version"
                version = action.split("@")[1]
                assert version != "latest", \
                    f"Action {action} should not use 'latest' tag"

    def test_no_hardcoded_secrets(self, workflow_content):
        """Verify no hardcoded secrets in the workflow file."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        import json
        workflow_str = json.dumps(steps).lower()
        # Check for common patterns of hardcoded secrets
        assert "password:" not in workflow_str or "secrets." in workflow_str, \
            "Should not have hardcoded passwords"
        assert "token:" not in workflow_str or "secrets." in workflow_str, \
            "Should not have hardcoded tokens"

    def test_uses_github_token_not_pat(self, workflow_content):
        """Verify workflow uses GITHUB_TOKEN, not personal access token."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        login_step = steps[2]
        password = login_step["with"]["password"]
        assert "GITHUB_TOKEN" in password, \
            "Should use GITHUB_TOKEN for authentication"


class TestWorkflowIntegrity:
    """Test overall workflow integrity and completeness."""

    def test_workflow_has_all_required_keys(self, workflow_content):
        """Verify workflow has all required top-level keys."""
        assert "name" in workflow_content, "Workflow must have 'name' key"
        # Note: 'on' is converted to True by PyYAML (YAML boolean)
        triggers = get_workflow_triggers(workflow_content)
        assert triggers is not None, "Workflow must have trigger configuration ('on' key)"
        assert "jobs" in workflow_content, "Workflow must have 'jobs' key"

    def test_job_has_all_required_keys(self, workflow_content):
        """Verify job has all required keys."""
        job = workflow_content["jobs"]["build-and-push"]
        required_keys = ["runs-on", "permissions", "steps"]
        for key in required_keys:
            assert key in job, f"Job must have '{key}' key"

    def test_no_syntax_errors_in_expressions(self, workflow_content):
        """Verify GitHub expressions have proper syntax."""
        import json
        workflow_str = json.dumps(workflow_content)
        # Check that all ${{ expressions have matching }}
        # Note: }} can appear in strings without ${{ (e.g., in step outputs)
        # So we check that every ${{ has a corresponding }} somewhere after it
        open_count = workflow_str.count("${{")
        # Count }} that appear after a ${{
        close_count = 0
        remaining_str = workflow_str
        while "${{" in remaining_str:
            idx = remaining_str.index("${{")
            remaining_str = remaining_str[idx+3:]
            if "}}" in remaining_str:
                close_count += 1
                remaining_str = remaining_str[remaining_str.index("}}")+2:]
            else:
                break
        assert open_count == close_count, \
            f"Expression syntax mismatch: {open_count} ${{{{ but only {close_count} properly closed"


class TestEdgeCasesAndRobustness:
    """Test edge cases and workflow robustness."""

    def test_workflow_handles_concurrent_runs(self, workflow_content):
        """Verify workflow configuration for concurrent runs."""
        # By default, workflows can run concurrently
        # This test verifies there's no concurrency group that would cause issues
        # If concurrency is added in the future, it should be intentional
        if "concurrency" in workflow_content:
            concurrency = workflow_content["concurrency"]
            assert "group" in concurrency, \
                "Concurrency configuration should specify a group"

    def test_registry_url_is_valid(self, workflow_content):
        """Verify registry URL is valid."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        login_step = steps[2]
        registry = login_step["with"]["registry"]
        assert registry.startswith("ghcr.io"), \
            "Registry should be ghcr.io"
        assert not registry.endswith("/"), \
            "Registry URL should not end with slash"

    def test_image_name_format_is_valid(self, workflow_content):
        """Verify image name format follows Docker conventions."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        metadata_step = steps[3]
        images = metadata_step["with"]["images"]
        # Should be in format: ghcr.io/owner/repo
        # Note: github.repository includes owner/repo, so we see 1 slash before it expands
        assert "ghcr.io/" in images, "Image name should start with ghcr.io/"
        assert "github.repository" in images, \
            "Image name should use github.repository variable"

    def test_tag_configuration_produces_valid_tags(self, workflow_content):
        """Verify tag configuration will produce valid Docker tags."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        metadata_step = steps[3]
        tags_config = metadata_step["with"]["tags"]
        # Should have multiple tag types for flexibility
        tag_types = [line.strip() for line in tags_config.split("\n") if line.strip()]
        assert len(tag_types) >= 2, \
            "Should have at least 2 tag types configured"

    def test_build_context_path_is_valid(self, workflow_content):
        """Verify build context path is valid."""
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        build_step = steps[4]
        context = build_step["with"]["context"]
        # '.' is the most common and safe context path
        assert context == ".", \
            "Build context should typically be '.'"


class TestRegressionPrevention:
    """Test to prevent regression of known issues."""

    def test_buildx_setup_is_present(self, workflow_content):
        """
        Regression test: Ensure setup-buildx-action is present.

        This prevents the issue where GHA cache export doesn't work
        without buildx setup. This was fixed in commit 9a3623b.
        """
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        buildx_steps = [s for s in steps if "setup-buildx-action" in s.get("uses", "")]
        assert len(buildx_steps) == 1, \
            "Must have exactly one setup-buildx-action step for GHA cache"

    def test_cache_configuration_is_present(self, workflow_content):
        """
        Regression test: Ensure cache configuration exists.

        Verifies that cache-from and cache-to are configured to prevent
        regression where builds are slow due to missing cache.
        """
        steps = workflow_content["jobs"]["build-and-push"]["steps"]
        build_step = steps[4]
        assert "cache-from" in build_step["with"], \
            "cache-from must be configured for build performance"
        assert "cache-to" in build_step["with"], \
            "cache-to must be configured for build performance"

    def test_permissions_are_explicit(self, workflow_content):
        """
        Regression test: Ensure permissions are explicitly set.

        Prevents regression where overly broad permissions are granted.
        Explicit permissions follow security best practices.
        """
        job = workflow_content["jobs"]["build-and-push"]
        assert "permissions" in job, \
            "Permissions must be explicitly declared"
        permissions = job["permissions"]
        # Should be explicit, not use default-all
        assert isinstance(permissions, dict), \
            "Permissions should be explicitly specified as dict"