# Tests for SynosCD schema and reconciler

import pytest
import yaml
from synoscd.schema import App, Project, parse_resource


def test_parse_app_from_yaml():
    """Test parsing an App resource from YAML."""
    yaml_str = """
apiVersion: synoscd.io/v1alpha1
kind: App
metadata:
  name: test-app
  labels:
    synoscd.io/managed: "true"
spec:
  containers:
    - name: main
      image: myapp:latest
      cpu: 0.5
      memory: 1Gi
  ingress:
    enabled: true
    targetPort: 8080
"""
    data = yaml.safe_load(yaml_str)
    app = parse_resource(data)

    assert isinstance(app, App)
    assert app.metadata.name == "test-app"
    assert app.spec.containers[0].image == "myapp:latest"
    assert app.spec.ingress.enabled is True


def test_parse_project_from_yaml():
    """Test parsing a Project resource from YAML."""
    yaml_str = """
apiVersion: synoscd.io/v1alpha1
kind: Project
metadata:
  name: my-project
spec:
  apps:
    - app-1
    - app-2
"""
    data = yaml.safe_load(yaml_str)
    project = parse_resource(data)

    assert isinstance(project, Project)
    assert project.metadata.name == "my-project"
    assert len(project.spec.apps) == 2


def test_app_validation():
    """Test that App schema validates required fields."""
    # Missing required containers field
    with pytest.raises(Exception):
        App(
            metadata={"name": "invalid-app"},
            spec={},
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
