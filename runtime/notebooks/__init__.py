# SPDX-License-Identifier: MIT
"""Governed external notebook provider contracts and implementations."""

from .contract import (
    AudioOverviewReceipt,
    AudioOverviewRequest,
    GoogleDriveSourceRequest,
    NotebookAccessScope,
    NotebookCreateRequest,
    NotebookFailureClass,
    NotebookProvider,
    NotebookProviderCapabilities,
    NotebookProviderError,
    NotebookReceipt,
    NotebookScopeKind,
    NotebookSourceReceipt,
    NotebookSourceRequest,
    PrincipalResolver,
    ProviderApiMaturity,
    TextSourceRequest,
    WebSourceRequest,
)
from .gemini_enterprise import GeminiNotebookEnterpriseProvider
from .google_identity import (
    DRIVE_SOURCE_SCOPE,
    GoogleUserInfoPrincipalResolver,
    NOTEBOOK_OAUTH_SCOPES,
)

__all__ = [
    "AudioOverviewReceipt",
    "AudioOverviewRequest",
    "DRIVE_SOURCE_SCOPE",
    "GeminiNotebookEnterpriseProvider",
    "GoogleDriveSourceRequest",
    "GoogleUserInfoPrincipalResolver",
    "NOTEBOOK_OAUTH_SCOPES",
    "NotebookAccessScope",
    "NotebookCreateRequest",
    "NotebookFailureClass",
    "NotebookProvider",
    "NotebookProviderCapabilities",
    "NotebookProviderError",
    "NotebookReceipt",
    "NotebookScopeKind",
    "NotebookSourceReceipt",
    "NotebookSourceRequest",
    "PrincipalResolver",
    "ProviderApiMaturity",
    "TextSourceRequest",
    "WebSourceRequest",
]
