FROM ubuntu:noble
LABEL maintainer="Odoo S.A. <info@odoo.com>"

SHELL ["/bin/bash", "-xo", "pipefail", "-c"]

# Generate locale C.UTF-8 for postgres and general locale data
ENV LANG=en_US.UTF-8

# Retrieve the target architecture to install the correct wkhtmltopdf package
ARG TARGETARCH

# Build arguments for user/group IDs to match host user
ARG USER_ID=1000
ARG GROUP_ID=1000


RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive \
    apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        make \
        libssl-dev \
        zlib1g-dev \
        libbz2-dev \
        libreadline-dev \
        libsqlite3-dev \
        libncursesw5-dev \
        xz-utils \
        tk-dev \
        libxml2-dev \
        libxmlsec1-dev \
        libffi-dev \
        liblzma-dev \
        libgdbm-dev \
        python3-pip \
        python3-dev \
        python3-venv \
        libgdbm-compat-dev \
        psmisc \
        libnss3-dev \
        libdb-dev \
        uuid-dev \
        git \
        wget \
        ca-certificates \
        curl \
        dirmngr \
        fonts-noto-cjk \
        gnupg \
        node-less \
        npm \
    openssh-client \
    && if [ -z "${TARGETARCH}" ]; then \
        TARGETARCH="$(dpkg --print-architecture)"; \
    fi \
    && WKHTMLTOPDF_ARCH=${TARGETARCH} \
    && case ${TARGETARCH} in \
        "amd64") WKHTMLTOPDF_ARCH=amd64 && WKHTMLTOPDF_SHA=967390a759707337b46d1c02452e2bb6b2dc6d59 ;; \
        "arm64") WKHTMLTOPDF_SHA=90f6e69896d51ef77339d3f3a20f8582bdf496cc ;; \
        "ppc64le" | "ppc64el") WKHTMLTOPDF_ARCH=ppc64el && WKHTMLTOPDF_SHA=5312d7d34a25b321282929df82e3574319aed25c ;; \
    esac \
    && curl -o wkhtmltox.deb -sSL https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.jammy_${WKHTMLTOPDF_ARCH}.deb \
    && echo ${WKHTMLTOPDF_SHA} wkhtmltox.deb | sha1sum -c - \
    && apt-get install -y --no-install-recommends ./wkhtmltox.deb \
    && rm -rf /var/lib/apt/lists/* wkhtmltox.deb

RUN echo 'deb http://apt.postgresql.org/pub/repos/apt/ noble-pgdg main' > /etc/apt/sources.list.d/pgdg.list \
    && GNUPGHOME="$(mktemp -d)" \
    && export GNUPGHOME \
    && repokey='B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8' \
    && gpg --batch --keyserver keyserver.ubuntu.com --recv-keys "${repokey}" \
    && gpg --batch --armor --export "${repokey}" > /etc/apt/trusted.gpg.d/pgdg.gpg.asc \
    && gpgconf --kill all \
    && rm -rf "$GNUPGHOME" \
    && apt-get update  \
    && apt-get install --no-install-recommends -y postgresql-client \
    && rm -f /etc/apt/sources.list.d/pgdg.list \
    && rm -rf /var/lib/apt/lists/*

# Install rtlcss (on Debian buster)
RUN npm install -g rtlcss

# Install Odoo using official commands
RUN wget -q -O - https://nightly.odoo.com/odoo.key | gpg --dearmor -o /usr/share/keyrings/odoo-archive-keyring.gpg \
    && echo 'deb [signed-by=/usr/share/keyrings/odoo-archive-keyring.gpg] https://nightly.odoo.com/18.0/nightly/deb/ ./' > /etc/apt/sources.list.d/odoo.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends odoo \
    && rm -rf /var/lib/apt/lists/*

# ...existing code...

# Copy entrypoint script and Odoo configuration file
COPY ./entrypoint.sh /
COPY ./odoo.conf /etc/odoo/
COPY ./start-odoo.sh /usr/local/bin/
COPY ./start-odoo-debug.sh /usr/local/bin/

# Set permissions and Mount /var/lib/odoo to allow restoring filestore and /mnt/extra-addons for users addons
RUN chmod +x /entrypoint.sh \
    && chmod +x /usr/local/bin/start-odoo.sh \
    && chmod +x /usr/local/bin/start-odoo-debug.sh \
    && chown odoo /etc/odoo/odoo.conf \
    && mkdir -p /mnt/extra-addons \
    && chown -R odoo /mnt/extra-addons
VOLUME ["/var/lib/odoo", "/mnt/extra-addons"]

# Expose Odoo services and debugpy port
EXPOSE 8069 8071 8072 5678

# Set the default config file
ENV ODOO_RC=/etc/odoo/odoo.conf

COPY wait-for-psql.py /usr/local/bin/wait-for-psql.py

# Set execute permissions for wait-for-psql.py
RUN chmod +x /usr/local/bin/wait-for-psql.py

# Install sudo and configure odoo user
RUN apt-get update \
    && apt-get install -y --no-install-recommends sudo \
    && echo "odoo ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers \
    && GROUP_NAME=$(getent group ${GROUP_ID} | cut -d: -f1) \
    && if [ -n "$GROUP_NAME" ]; then \
        usermod -a -G $GROUP_NAME odoo; \
    fi \
    && usermod -s /bin/bash odoo \
        && mkdir -p /home/odoo \
        && chown -R odoo:odoo /home/odoo \
    && chown -R odoo:odoo /var/lib/odoo \
    && chown -R odoo:odoo /mnt/extra-addons \
    && rm -rf /var/lib/apt/lists/*

# Set default user when running the container
USER odoo

# Setup bashrc to activate venv automatically
RUN echo 'if [ -f /home/odoo/venv/bin/activate ]; then source /home/odoo/venv/bin/activate; fi' >> /home/odoo/.bashrc

ENTRYPOINT ["/entrypoint.sh"]
CMD ["sleep", "infinity"]
