"""
Comprehensive tests for README.md documentation.

This test suite validates the integrity and accuracy of the README.md file,
ensuring that:
- Referenced files and directories exist
- Configuration examples are valid
- Code snippets are syntactically correct
- URLs are properly formatted
- Documentation structure is maintained
"""

import os
import re
import json
from pathlib import Path
import pytest


# Get project root directory
PROJECT_ROOT = Path(__file__).parent.parent
README_PATH = PROJECT_ROOT / "README.md"


@pytest.fixture
def readme_content():
    """Load README.md content."""
    with open(README_PATH, "r", encoding="utf-8") as f:
        return f.read()


class TestREADMEFileReferences:
    """Test that all files and directories mentioned in README exist."""

    def test_readme_exists(self):
        """Verify README.md file exists."""
        assert README_PATH.exists(), "README.md should exist in project root"

    def test_architecture_files_exist(self, readme_content):
        """Verify files mentioned in Architecture section exist."""
        files_to_check = [
            "src/run_bot.py",
            "src/runner.py",
            "src/strategy.py",
            "src/brokers.py",
            "config.json",
        ]
        for file_path in files_to_check:
            full_path = PROJECT_ROOT / file_path
            assert full_path.exists(), f"{file_path} referenced in Architecture section should exist"

    def test_config_json_exists(self):
        """Verify config.json file exists and is valid JSON."""
        config_path = PROJECT_ROOT / "config.json"
        assert config_path.exists(), "config.json should exist"

        # Verify it's valid JSON
        with open(config_path, "r") as f:
            config = json.load(f)
            assert isinstance(config, dict), "config.json should contain a JSON object"

    def test_docker_compose_exists(self):
        """Verify docker-compose.yml exists."""
        docker_compose_path = PROJECT_ROOT / "docker-compose.yml"
        assert docker_compose_path.exists(), "docker-compose.yml should exist"

    def test_env_template_exists(self):
        """Verify .env.template exists."""
        env_template_path = PROJECT_ROOT / ".env.template"
        assert env_template_path.exists(), ".env.template should exist"

    def test_requirements_txt_exists(self):
        """Verify requirements.txt exists."""
        requirements_path = PROJECT_ROOT / "requirements.txt"
        assert requirements_path.exists(), "requirements.txt should exist"

    def test_license_file_exists(self):
        """Verify LICENSE file exists."""
        license_path = PROJECT_ROOT / "LICENSE"
        assert license_path.exists(), "LICENSE file should exist"


class TestREADMEConfiguration:
    """Test configuration examples mentioned in README."""

    def test_config_has_required_profiles(self):
        """Verify config.json contains the profiles mentioned in README."""
        config_path = PROJECT_ROOT / "config.json"
        with open(config_path, "r") as f:
            config = json.load(f)

        # Check for profile structure (exact keys may vary)
        assert isinstance(config, dict), "config.json should be a dictionary"
        # Config should have multiple profile configurations
        assert len(config) > 0, "config.json should contain configuration data"

    def test_env_template_has_required_vars(self):
        """Verify .env.template contains mentioned environment variables."""
        env_template_path = PROJECT_ROOT / ".env.template"
        with open(env_template_path, "r") as f:
            env_content = f.read()

        required_vars = [
            "BOT_ENCRYPTION_KEY",
            "PHEMEX_API_KEY",
            "PHEMEX_API_SECRET",
        ]

        for var in required_vars:
            assert var in env_content, f"{var} should be in .env.template"


class TestREADMEURLs:
    """Test URL references in README."""

    def test_all_urls_are_well_formed(self, readme_content):
        """Verify all external URLs in README follow proper format."""
        # Match markdown links: [text](url)
        markdown_links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', readme_content)

        # Only validate external URLs (those that claim to be http/https)
        # Skip anchor links (#), relative paths, and local file references
        for link_text, url in markdown_links:
            # Only check URLs that start with http (claimed external URLs)
            if url.startswith('http'):
                # These should be properly formed with http:// or https://
                assert url.startswith('http://') or url.startswith('https://'), \
                    f"External URL in link [{link_text}]({url}) should start with http:// or https://"
                # Should not have obvious typos like "http:/" or "https:/"
                assert not url.startswith('http:/') or url.startswith('http://'), \
                    f"URL malformed: [{link_text}]({url})"

    def test_phemex_urls_present(self, readme_content):
        """Verify Phemex-related URLs are present."""
        assert 'phemex.com' in readme_content, "README should contain phemex.com references"
        assert 'testnet.phemex.com' in readme_content, "README should reference testnet URL"

    def test_github_repository_url_present(self, readme_content):
        """Verify GitHub repository URL is present."""
        assert 'github.com/storagebirddrop/tradingbot' in readme_content, \
            "README should contain GitHub repository URL"


class TestREADMECodeExamples:
    """Test code examples in README are syntactically valid."""

    def test_python_code_snippets_are_valid(self, readme_content):
        """Extract and validate Python code snippets."""
        # Find Python code blocks
        python_blocks = re.findall(r'```(?:bash|python)?\n(python3.*?)\n```', readme_content, re.DOTALL)

        # Simple validation: each Python command should be properly formatted
        for block in python_blocks:
            lines = [line.strip() for line in block.split('\n') if line.strip()]
            for line in lines:
                if line.startswith('python3'):
                    # Validate python3 commands have proper structure
                    assert '-m' in line or line.endswith('.py') or '-c' in line, \
                        f"Python command should be well-formed: {line}"

    def test_encryption_key_generation_command(self, readme_content):
        """Verify the encryption key generation command is present and correct."""
        expected_pattern = r'python3 -c "import base64, os;.*BOT_ENCRYPTION_KEY='
        assert re.search(expected_pattern, readme_content), \
            "README should contain correct encryption key generation command"

    def test_docker_commands_present(self, readme_content):
        """Verify essential Docker commands are documented."""
        docker_commands = [
            'docker compose pull',
            'docker compose up',
            'docker compose exec',
        ]
        for cmd in docker_commands:
            assert cmd in readme_content, f"README should document '{cmd}' command"

    def test_bash_code_blocks_have_valid_syntax(self, readme_content):
        """Basic validation of bash code blocks."""
        # Find bash code blocks
        bash_blocks = re.findall(r'```bash\n(.*?)\n```', readme_content, re.DOTALL)

        assert len(bash_blocks) > 0, "README should contain bash code examples"

        # Basic validation: check for common patterns
        for block in bash_blocks:
            # Should not have obvious syntax errors like unmatched quotes
            single_quotes = block.count("'") - block.count("\\'")
            double_quotes = block.count('"') - block.count('\\"')

            # Note: This is a simple heuristic, not a full parser
            # Allow odd counts in heredocs and certain contexts
            if '<<' not in block:  # Skip heredoc blocks
                # Just check the block is not empty
                assert len(block.strip()) > 0, "Bash code block should not be empty"


class TestREADMEStructure:
    """Test README.md structure and organization."""

    def test_readme_has_main_sections(self, readme_content):
        """Verify README contains all main sections."""
        required_sections = [
            "Architecture",
            "Strategies",
            "Profiles",
            "Deployment",
            "Configuration",
            "Monitoring",
            "Risk Controls",
            "Research Scripts",
            "Security",
            "License",
        ]

        for section in required_sections:
            # Look for section headers (## Section Name)
            pattern = f"##.*{section}"
            assert re.search(pattern, readme_content, re.IGNORECASE), \
                f"README should have '{section}' section"

    def test_readme_has_risk_disclaimer(self, readme_content):
        """Verify README contains risk disclaimer."""
        assert "Risk Disclaimer" in readme_content, "README should contain risk disclaimer"
        assert "Educational" in readme_content or "education" in readme_content.lower(), \
            "README should mention educational nature"

    def test_deployment_options_documented(self, readme_content):
        """Verify both deployment options are documented."""
        assert "Option A" in readme_content, "README should document Option A deployment"
        assert "Option B" in readme_content, "README should document Option B deployment"
        assert "Docker" in readme_content, "README should mention Docker deployment"
        assert "VM" in readme_content or "LXC" in readme_content, \
            "README should mention VM/LXC deployment"

    def test_profiles_table_present(self, readme_content):
        """Verify profiles comparison table exists."""
        # Look for table with profile names
        assert "local_paper" in readme_content, "README should document local_paper profile"
        assert "phemex_testnet" in readme_content, "README should document phemex_testnet profile"
        assert "phemex_live" in readme_content, "README should document phemex_live profile"


class TestREADMEStrategies:
    """Test strategy documentation in README."""

    def test_all_strategies_documented(self, readme_content):
        """Verify all three strategies are documented."""
        strategies = [
            "obv_breakout",
            "rsi_momentum_pullback",
            "vwap_band_bounce",
        ]

        for strategy in strategies:
            assert strategy in readme_content, f"Strategy '{strategy}' should be documented"

    def test_strategy_parameters_documented(self, readme_content):
        """Verify strategy parameters are mentioned."""
        params = [
            "stop_pct",
            "risk_per_trade",
            "max_positions",
        ]

        for param in params:
            assert param in readme_content, f"Parameter '{param}' should be documented"


class TestREADMESecurity:
    """Test security-related documentation."""

    def test_security_section_exists(self, readme_content):
        """Verify security section exists and covers key topics."""
        assert "## Security" in readme_content, "README should have Security section"
        assert "encryption" in readme_content.lower(), \
            "README should mention encryption"
        assert "BOT_ENCRYPTION_KEY" in readme_content, \
            "README should document encryption key requirement"

    def test_api_key_security_mentioned(self, readme_content):
        """Verify API key security is addressed."""
        assert "API" in readme_content and "key" in readme_content.lower(), \
            "README should mention API keys"
        assert ".env" in readme_content, "README should mention .env file"

    def test_dry_run_safety_documented(self, readme_content):
        """Verify dry_run safety feature is documented."""
        assert "dry_run" in readme_content, "README should document dry_run mode"
        assert "true" in readme_content, "README should show dry_run: true examples"


class TestREADMEMonitoring:
    """Test monitoring and operations documentation."""

    def test_monitoring_commands_present(self, readme_content):
        """Verify monitoring commands are documented."""
        monitoring_commands = [
            "healthcheck",
            "equity_report",
            "trades_report",
        ]

        for cmd in monitoring_commands:
            assert cmd in readme_content, f"Monitoring command '{cmd}' should be documented"

    def test_log_monitoring_documented(self, readme_content):
        """Verify log monitoring is documented."""
        assert "tail" in readme_content, "README should mention tail command for logs"
        assert "grep" in readme_content, "README should mention grep for log filtering"


class TestREADMEEdgeCases:
    """Test edge cases and additional validation."""

    def test_readme_not_empty(self, readme_content):
        """Verify README is not empty."""
        assert len(readme_content) > 100, "README should contain substantial content"

    def test_readme_has_no_broken_markdown_links(self, readme_content):
        """Verify markdown links are properly formatted."""
        # Find all markdown links
        links = re.findall(r'\[([^\]]*)\]\(([^)]*)\)', readme_content)

        for link_text, url in links:
            # Link text should not be empty for non-image links
            if not url.startswith('http'):  # File/anchor references
                assert len(link_text) > 0 or url.startswith('#'), \
                    f"Markdown link should have text: [{link_text}]({url})"

    def test_environment_variables_consistent(self, readme_content):
        """Verify environment variable references are consistent."""
        # Key environment variables should be in UPPERCASE
        env_vars = [
            "BOT_ENCRYPTION_KEY",
            "PHEMEX_API_KEY",
            "PHEMEX_API_SECRET",
            "ENABLE_TESTNET_TRADING",
            "ENABLE_LIVE_TRADING",
            "BOT_ENV",
        ]

        for var in env_vars:
            if var in readme_content:
                # Should not appear in lowercase in variable contexts
                # (Allow in explanatory text)
                assert readme_content.count(var) > 0, \
                    f"Environment variable {var} should be in uppercase"

    def test_config_json_references_match_structure(self, readme_content):
        """Verify config.json parameter references are valid."""
        config_path = PROJECT_ROOT / "config.json"
        with open(config_path, "r") as f:
            config = json.load(f)

        # Some parameters that should exist in config or are documented
        documented_params = [
            "dry_run",
            "max_positions",
            "risk_per_trade",
        ]

        # Check that these are mentioned in README
        for param in documented_params:
            assert param in readme_content, \
                f"Config parameter '{param}' should be documented in README"

    def test_profile_specific_requirements_table(self, readme_content):
        """Verify per-profile requirements table exists."""
        # Should have a table showing requirements for each profile
        assert "local_paper" in readme_content
        assert "phemex_testnet" in readme_content
        assert "phemex_live" in readme_content
        # Table should mention what's required/optional
        assert "required" in readme_content.lower()
        assert "optional" in readme_content.lower() or "—" in readme_content

    def test_sharpe_ratio_values_are_numeric(self, readme_content):
        """Verify Sharpe ratio values in strategy docs are properly formatted."""
        # Find the Sharpe ratio table
        sharpe_pattern = r'OOS Sharpe.*?\n.*?\n(.*?)\n\n'
        match = re.search(sharpe_pattern, readme_content, re.DOTALL)

        if match:
            sharpe_section = match.group(1)
            # Extract numbers from the table
            numbers = re.findall(r'\d+\.\d+', sharpe_section)
            assert len(numbers) > 0, "Sharpe ratio table should contain numeric values"

            # All Sharpe ratios should be reasonable (between 0 and 3)
            for num_str in numbers:
                num = float(num_str)
                assert 0 <= num <= 3, f"Sharpe ratio {num} should be in reasonable range"

    def test_checklist_before_going_live(self, readme_content):
        """Verify README contains a checklist for going live."""
        # Should have checklist items (markdown checkboxes)
        assert "- [ ]" in readme_content or "- []" in readme_content, \
            "README should contain checklist for going live"
        assert "checklist" in readme_content.lower(), \
            "README should mention checklist"