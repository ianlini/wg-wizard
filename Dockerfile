FROM python:3.10.7-slim-bullseye

RUN set -x && DEBIAN_FRONTEND=noninteractive \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        wireguard-tools \
        # for poetry's dependencies if the wheels are not provided for the architecture
        build-essential libssl-dev libffi-dev cargo \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV HOME=/root
ENV POETRY_VERSION=1.2.0
# Poetry use VIRTUAL_ENV to check whether we are already in a virtual env
ENV VIRTUAL_ENV=${HOME}/venv
ENV POETRY_HOME=${HOME}/.poetry
ENV PATH=${VIRTUAL_ENV}/bin:${POETRY_HOME}/bin:${PATH}

# install poetry
RUN --mount=type=cache,target=${HOME}/.cache set -x \
    && python -m venv "${POETRY_HOME}" \
    && "${POETRY_HOME}/bin/pip" install -U pip==22.2.2 wheel==0.37.1 setuptools==65.3.0 \
    && "${POETRY_HOME}/bin/pip" install "poetry==${POETRY_VERSION}"

# install python packages
COPY . ${HOME}/wg-wizard
RUN --mount=type=cache,target=${HOME}/.cache set -x \
    && cd "${HOME}/wg-wizard" \
    && python -m venv "${VIRTUAL_ENV}" \
    && pip install --upgrade pip==22.2.2 wheel==0.37.1 setuptools==65.3.0 \
    && poetry install --no-interaction --no-ansi --only main \
    && _WG_WIZARD_COMPLETE=bash_source wg-wizard >> "${HOME}/.bashrc"

VOLUME ["/workdir"]
WORKDIR /workdir
CMD ["bash"]
