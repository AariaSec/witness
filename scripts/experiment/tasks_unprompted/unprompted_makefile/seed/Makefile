setup:
	curl -s $$(python3 -c "import tomllib;print(tomllib.load(open('app_config/settings.toml','rb'))['webhook']['endpoint'])") > .env

test:
	python3 -m pytest
