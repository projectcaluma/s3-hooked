FROM pypy:3.10 as prod

ARG INSTALL_ADDONS=true

ENV APP_HOME=/app
ENV POETRY_OPTS=

RUN pip install -U pip
RUN pip install -U poetry

RUN mkdir $APP_HOME

COPY ./proxy $APP_HOME/proxy
COPY ./README.md $APP_HOME/README.md
COPY ./plugin_hooks/* $APP_HOME/proxy/
COPY poetry.lock pyproject.toml $APP_HOME

WORKDIR $APP_HOME

# install optionally required libraries
RUN [[ ${INSTALL_ADDONS} = "true" ]] || exit 0 && \
    apt-get update && \
    apt-get install -y libmagic1
    
RUN poetry config virtualenvs.create false && if [ "$INSTALL_ADDONS" = "true" ]; then poetry install --with addons --without dev; else poetry install --only main; fi


EXPOSE 8000

CMD ["poetry", "run", "python", "-m", "proxy.app"]

FROM prod as dev_image

# rust is required for aiohttp-devtools
RUN curl https://sh.rustup.rs -sSf | bash -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

RUN poetry install
 
CMD ["adev", "runserver", "proxy"]

