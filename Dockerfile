FROM python:3.10.7-slim-bullseye

ARG TARGETPLATFORM
RUN set -x && DEBIAN_FRONTEND=noninteractive \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        wireguard-tools \
    && { \
      if [ "${TARGETPLATFORM}" = 'linux/arm/v7' ]; then \
        # for poetry's dependencies if the wheels are not provided for the architecture
        apt-get install -y --no-install-recommends \
          build-essential libssl-dev libffi-dev cargo; \
      fi; \
    } \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV HOME=/root
ENV POETRY_VERSION=1.3.2
# Poetry use VIRTUAL_ENV to check whether we are already in a virtual env
ENV VIRTUAL_ENV=${HOME}/venv
ENV POETRY_HOME=${HOME}/.poetry
ENV PATH=${VIRTUAL_ENV}/bin:${POETRY_HOME}/bin:${PATH}
# https://github.com/rust-lang/cargo/issues/10303
ENV CARGO_NET_GIT_FETCH_WITH_CLI=true

# install poetry
RUN --mount=type=cache,target=${HOME}/.cache --mount=type=cache,target=${HOME}/.cargo set -x \
    && python -m venv "${POETRY_HOME}" \
    && "${POETRY_HOME}/bin/pip" install -U pip==22.3.1 wheel==0.38.4 setuptools==66.1.1 \
    && "${POETRY_HOME}/bin/pip" install "poetry==${POETRY_VERSION}"

# install python packages
COPY pyproject.toml poetry.lock /tmp/poetry/
RUN --mount=type=cache,target=${HOME}/.cache set -x \
    && cd /tmp/poetry/ \
    && python -m venv "${VIRTUAL_ENV}" \
    && pip install --upgrade pip==22.3.1 wheel==0.38.4 setuptools==66.1.1 \
    && poetry install --no-interaction --no-ansi --only main --no-root \
    && rm -rf /tmp/poetry/

# install the root package
COPY . ${HOME}/wg-wizard
RUN --mount=type=cache,target=${HOME}/.cache set -x \
    && cd "${HOME}/wg-wizard" \
    && poetry install --no-interaction --no-ansi --only main \
    && _WG_WIZARD_COMPLETE=bash_source wg-wizard >> "${HOME}/.bashrc"

VOLUME ["/workdir"]
WORKDIR /workdir
CMD ["bash"]
