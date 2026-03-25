"""
Tests for evaluation_tools module.

Tests PVMAP comparison and ground truth discovery wrappers.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.tools.evaluation_tools import (
    is_pvmap_filename,
    find_ground_truth_pvmaps,
    compare_pvmaps,
    select_best_ground_truth
)


def test_is_pvmap_filename():
    """Test PVMAP filename detection."""
    # Valid PVMAP names
    assert is_pvmap_filename("pvmap.csv") is True
    assert is_pvmap_filename("pv_map.csv") is True
    assert is_pvmap_filename("dataset_pvmap.csv") is True
    assert is_pvmap_filename("generated_PVMAP.csv") is True

    # Invalid names
    assert is_pvmap_filename("metadata.csv") is False
    assert is_pvmap_filename("pvmap.txt") is False
    assert is_pvmap_filename("data.csv") is False


def test_find_ground_truth_pvmaps_explicit(temp_dir):
    """Test finding ground truth with explicit path."""
    pvmap_file = temp_dir / "explicit_pvmap.csv"
    pvmap_file.write_text("key,property,value\n")

    result = find_ground_truth_pvmaps(
        dataset_name="test_dataset",
        explicit_pvmap=pvmap_file
    )

    assert result['success'] is True
    assert result['count'] == 1
    assert result['pvmaps'][0] == pvmap_file
    assert result['error'] is None


def test_find_ground_truth_pvmaps_explicit_missing(temp_dir):
    """Test explicit path that doesn't exist."""
    pvmap_file = temp_dir / "nonexistent.csv"

    result = find_ground_truth_pvmaps(
        dataset_name="test_dataset",
        explicit_pvmap=pvmap_file
    )

    assert result['success'] is False
    assert result['count'] == 0
    assert "not found" in result['error']


def test_find_ground_truth_pvmaps_in_search_dir(temp_dir):
    """Test finding PVMAP in search directory."""
    # Create directory structure
    search_dir = temp_dir / "ground_truth"
    dataset_dir = search_dir / "test_dataset"
    dataset_dir.mkdir(parents=True)

    # Create PVMAP file
    pvmap_file = dataset_dir / "pvmap.csv"
    pvmap_file.write_text("key,property,value\n")

    result = find_ground_truth_pvmaps(
        dataset_name="test_dataset",
        search_dir=search_dir
    )

    assert result['success'] is True
    assert result['count'] == 1
    assert pvmap_file in result['pvmaps']


def test_find_ground_truth_pvmaps_multiple(temp_dir):
    """Test finding multiple ground truth PVMAPs."""
    # Create directory structure
    search_dir = temp_dir / "ground_truth"
    dataset_dir = search_dir / "brazil_sidra_ibge"
    dataset_dir.mkdir(parents=True)

    # Create multiple PVMAP files
    pvmap1 = dataset_dir / "population_pvmap.csv"
    pvmap1.write_text("key,property,value\n")

    pvmap2 = dataset_dir / "income_pvmap.csv"
    pvmap2.write_text("key,property,value\n")

    result = find_ground_truth_pvmaps(
        dataset_name="brazil_sidra_ibge",
        search_dir=search_dir
    )

    assert result['success'] is True
    assert result['count'] == 2
    assert pvmap1 in result['pvmaps']
    assert pvmap2 in result['pvmaps']


def test_find_ground_truth_pvmaps_not_found(temp_dir):
    """Test when no ground truth PVMAP is found."""
    search_dir = temp_dir / "ground_truth"
    search_dir.mkdir()

    result = find_ground_truth_pvmaps(
        dataset_name="nonexistent_dataset",
        search_dir=search_dir
    )

    assert result['success'] is False
    assert result['count'] == 0
    assert "No ground truth PVMAP found" in result['error']


def test_find_ground_truth_pvmaps_in_source_repo(temp_dir):
    """Test finding PVMAP in source repo."""
    # Create repo structure
    source_repo = temp_dir / "datacommonsorg-data" / "ground_truth"
    dataset_dir = source_repo / "bis_central_bank"
    dataset_dir.mkdir(parents=True)

    # Create PVMAP
    pvmap_file = dataset_dir / "bis_pvmap.csv"
    pvmap_file.write_text("key,property,value\n")

    result = find_ground_truth_pvmaps(
        dataset_name="bis_central_bank",
        source_repo=source_repo
    )

    assert result['success'] is True
    assert result['count'] == 1
    assert pvmap_file in result['pvmaps']


@patch('src.tools.evaluation_tools._compare_pvmaps_diff')
def test_compare_pvmaps_success(mock_compare, temp_dir):
    """Test successful PVMAP comparison."""
    # Create test files
    auto_pvmap = temp_dir / "auto_pvmap.csv"
    auto_pvmap.write_text("key,property,value\n")

    gt_pvmap = temp_dir / "gt_pvmap.csv"
    gt_pvmap.write_text("key,property,value\n")

    output_dir = temp_dir / "output"

    # Mock comparison result
    mock_counters = {
        'nodes-ground-truth': 10,
        'nodes-matched': 9,
        'PVs-matched': 45,
        'pvs-modified': 3,
        'pvs-deleted': 2
    }
    mock_diff = "Diff output text"
    mock_compare.return_value = (mock_counters, mock_diff)

    result = compare_pvmaps(
        auto_pvmap_path=auto_pvmap,
        gt_pvmap_path=gt_pvmap,
        output_dir=output_dir
    )

    assert result['success'] is True
    assert result['error'] is None
    assert result['counters'] == mock_counters
    assert result['diff_text'] == mock_diff
    assert result['accuracy'] == 90.0  # 9/10 * 100
    assert result['pv_accuracy'] == 90.0  # 45/50 * 100


def test_compare_pvmaps_missing_auto(temp_dir):
    """Test comparison with missing auto PVMAP."""
    auto_pvmap = temp_dir / "nonexistent_auto.csv"
    gt_pvmap = temp_dir / "gt.csv"
    gt_pvmap.write_text("key,property,value\n")

    output_dir = temp_dir / "output"

    result = compare_pvmaps(
        auto_pvmap_path=auto_pvmap,
        gt_pvmap_path=gt_pvmap,
        output_dir=output_dir
    )

    assert result['success'] is False
    assert "not found" in result['error']


def test_compare_pvmaps_missing_gt(temp_dir):
    """Test comparison with missing ground truth."""
    auto_pvmap = temp_dir / "auto.csv"
    auto_pvmap.write_text("key,property,value\n")

    gt_pvmap = temp_dir / "nonexistent_gt.csv"

    output_dir = temp_dir / "output"

    result = compare_pvmaps(
        auto_pvmap_path=auto_pvmap,
        gt_pvmap_path=gt_pvmap,
        output_dir=output_dir
    )

    assert result['success'] is False
    assert "not found" in result['error']


@patch('src.tools.evaluation_tools._compare_pvmaps_diff')
def test_compare_pvmaps_exception(mock_compare, temp_dir):
    """Test comparison with exception."""
    auto_pvmap = temp_dir / "auto.csv"
    auto_pvmap.write_text("key,property,value\n")

    gt_pvmap = temp_dir / "gt.csv"
    gt_pvmap.write_text("key,property,value\n")

    output_dir = temp_dir / "output"

    # Mock exception
    mock_compare.side_effect = Exception("Comparison error")

    result = compare_pvmaps(
        auto_pvmap_path=auto_pvmap,
        gt_pvmap_path=gt_pvmap,
        output_dir=output_dir
    )

    assert result['success'] is False
    assert "failed" in result['error'].lower()


@patch('src.tools.evaluation_tools.compare_pvmaps')
def test_select_best_ground_truth(mock_compare, temp_dir):
    """Test selecting best ground truth from multiple."""
    auto_pvmap = temp_dir / "auto.csv"
    auto_pvmap.write_text("key,property,value\n")

    # Create multiple ground truth files
    gt1 = temp_dir / "gt1_pvmap.csv"
    gt1.write_text("key,property,value\n")

    gt2 = temp_dir / "gt2_pvmap.csv"
    gt2.write_text("key,property,value\n")

    gt3 = temp_dir / "gt3_pvmap.csv"
    gt3.write_text("key,property,value\n")

    output_dir = temp_dir / "eval"

    # Mock comparison results with different accuracies
    def side_effect(auto_pvmap_path, gt_pvmap_path, output_dir):
        if 'gt1' in str(gt_pvmap_path):
            return {
                'success': True,
                'accuracy': 75.0,
                'pv_accuracy': 80.0,
                'counters': {}
            }
        elif 'gt2' in str(gt_pvmap_path):
            return {
                'success': True,
                'accuracy': 95.0,  # Best match
                'pv_accuracy': 96.0,
                'counters': {}
            }
        else:
            return {
                'success': True,
                'accuracy': 85.0,
                'pv_accuracy': 87.0,
                'counters': {}
            }

    mock_compare.side_effect = side_effect

    result = select_best_ground_truth(
        auto_pvmap_path=auto_pvmap,
        gt_pvmaps=[gt1, gt2, gt3],
        output_base_dir=output_dir
    )

    assert result['success'] is True
    assert result['best_pvmap'] == gt2  # gt2 has highest accuracy
    assert result['best_accuracy'] == 95.0
    assert len(result['all_results']) == 3


def test_select_best_ground_truth_empty_list(temp_dir):
    """Test selecting with empty ground truth list."""
    auto_pvmap = temp_dir / "auto.csv"
    auto_pvmap.write_text("key,property,value\n")

    output_dir = temp_dir / "eval"

    result = select_best_ground_truth(
        auto_pvmap_path=auto_pvmap,
        gt_pvmaps=[],
        output_base_dir=output_dir
    )

    assert result['success'] is False
    assert "No ground truth PVMAPs provided" in result['error']
