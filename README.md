# DataKult
DataKult is multi-media database to track one's collection across a variety of art forms and media (books, movies, music, games, series, ...). 

## Why build DataKult?
Goodreads, Letterboxd, Backloggery or IGDB are fine services but some might say they are too narrow. Most people do not ONLY read books OR watch movies OR play games, they consume different forms of media and some would appreciate to track their comsumption and/or collection in a single UI.

## Getting started
DataKult is still in early development but you can still run the dev environment.

# Prerequisites
The project can be run with Django 2.2.* and Python 3.8.* but it is preferrable to run it in a Docker container.

- Docker
- Git

# Installing
Fork and/or clone this repo :

```
git clone https://github.com/PascalRepond/datakult.git
```

Build the server
```
docker-compose up -d --build
```
Go to:
```
https://localhost:8000
```

## Tech stack

- [Django](https://www.djangoproject.com/) for the app (front and back)
- [PostgreSQL](https://www.postgresql.org/) for the database
- [Docker](https://www.docker.com/) for environment and deployment

## Contributing
Contact [the author](https://github.com/PascalRepond) for any question or if you would like to contribute to the project.

## Authors
- __[Pascal Repond](https://github.com/PascalRepond)__ - _Idea and initial work_

## License
This project is licensed under the GNU [GPLv3](https://choosealicense.com/licenses/gpl-3.0/#) license. See [LICENSE.md](https://github.com/PascalRepond/datakult/blob/master/LICENSE.md) for more details. 