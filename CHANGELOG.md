# CHANGELOG

<!-- version list -->

## v1.4.0 (2026-01-12)

### Continuous Integration

- Remove unused dependencies and optimise CI workflows
  ([`824ca57`](https://github.com/PascalRepond/datakult/commit/824ca57658181b9e9dfceb41a764fd2c076e3d9c))

### Features

- Add saved views feature with filters and sorting
  ([`939e08f`](https://github.com/PascalRepond/datakult/commit/939e08f31d571455bc4b20f050734a2ae40103eb))

- Display version number in sidebar and header
  ([`8faf601`](https://github.com/PascalRepond/datakult/commit/8faf601d0ab7a4961954d85d236c78f7080bb3a7))


## v1.3.0 (2026-01-07)

### Bug Fixes

- Change language form
  ([`87dfb24`](https://github.com/PascalRepond/datakult/commit/87dfb24cff365e8080d3a62621c0336390458b70))

### Build System

- Update docker setup
  ([`3f6faed`](https://github.com/PascalRepond/datakult/commit/3f6faed7f4fb83b7b0b0e511a609e8fdf708d2de))

### Chores

- Migrate from heroicons to lucide icons
  ([`8770003`](https://github.com/PascalRepond/datakult/commit/8770003b8d893cf0f5e7684f1c0cb6cc967b5b8d))

- Translate new and updated strings
  ([`d719756`](https://github.com/PascalRepond/datakult/commit/d71975634a5a265f7aa9687c044203d977c0c9b5))

- Update dependencies
  ([`e45e823`](https://github.com/PascalRepond/datakult/commit/e45e823fdd083ac1501f0a8b1ae196a9c9331b88))

### Features

- **theming**: Add custom daisyUI themes
  ([`2d27904`](https://github.com/PascalRepond/datakult/commit/2d279043a2cdf73d1adf5c12185f1f447293ada4))

### Refactoring

- Extract helpers and enhance fixtures
  ([`bc0bd4b`](https://github.com/PascalRepond/datakult/commit/bc0bd4ba2563a47584b487ea2cb056b16c69b2ea))

- Reorganize templates into subdirectories
  ([`bc1a6ea`](https://github.com/PascalRepond/datakult/commit/bc1a6ea35ede595c6fe8a2b9f4840b1f1597f70c))

### Testing

- Optimise tests
  ([`ca12abe`](https://github.com/PascalRepond/datakult/commit/ca12abe8371f7eb521611c5183d5c5e81cd196d5))


## v1.2.2 (2026-01-05)

### Bug Fixes

- Back button in media detail and edit views
  ([`1b34afd`](https://github.com/PascalRepond/datakult/commit/1b34afda51305d81ca4fbb045189bdd12160f572))

### Refactoring

- Simplify filters with URL-based state and multi-select support
  ([`0c9bce9`](https://github.com/PascalRepond/datakult/commit/0c9bce9e5dc967f80d3e8568a427f1d7d1eae157))


## v1.2.1 (2026-01-04)

### Bug Fixes

- Display corrections
  ([`d67f49e`](https://github.com/PascalRepond/datakult/commit/d67f49eeaee5d6fedd13621ecca57d1403640c51))


## v1.2.0 (2026-01-04)

### Code Style

- **media_edit**: Improve markdown editor appearance
  ([`63cbe4d`](https://github.com/PascalRepond/datakult/commit/63cbe4d0bd842ff27edea91af4e132a9ad3c0659))

### Features

- Add a navigation sidebar
  ([`e6e7d08`](https://github.com/PascalRepond/datakult/commit/e6e7d085c5a819c3ef662a00d55f5556001b9a2f))

- **locale**: Add language switching and French translation
  ([`16d180a`](https://github.com/PascalRepond/datakult/commit/16d180aeaf3db670dc01d9908d49959740ba49d1))

- **media**: Improve media detail and edit templates
  ([`4c1026b`](https://github.com/PascalRepond/datakult/commit/4c1026b538ae0c76fa7786ee2fdc722d03ceade6))

- **ui**: Enhance media list views display
  ([`1af301d`](https://github.com/PascalRepond/datakult/commit/1af301d55f67a364e1c366a9f1fa07d78b94226c))

### Testing

- Fix setup script to render reviews
  ([`b8a74dd`](https://github.com/PascalRepond/datakult/commit/b8a74ddb483b0af27ad7101f19c7ec587d5fd2dc))


## v1.1.0 (2026-01-02)

### Bug Fixes

- Fix media serving in production
  ([`a67549e`](https://github.com/PascalRepond/datakult/commit/a67549edc14ad2a2cdba1993f8199023e7b76cdd))

### Features

- Enhance backup cron job
  ([`391b59a`](https://github.com/PascalRepond/datakult/commit/391b59a680318813bae06fecf9ff0511c32f76e0))


## v1.0.2 (2026-01-01)

### Bug Fixes

- Correct collectstatic for Docker
  ([`223d569`](https://github.com/PascalRepond/datakult/commit/223d569865a49885f983720f6f95698b26c3c80a))


## v1.0.1 (2026-01-01)

### Bug Fixes

- Resolve production deployment issues
  ([`1579838`](https://github.com/PascalRepond/datakult/commit/1579838f504f1f3df5fdea528a6df710527e8283))

### Continuous Integration

- Correct incorrect commit message template
  ([`cdb16e9`](https://github.com/PascalRepond/datakult/commit/cdb16e9df0e2a0274d0543f4213e27f70f30c03b))


## v1.0.0 (2026-01-01)

### Bug Fixes

- Correct staticfiles for test and debug
  ([`09e02f5`](https://github.com/PascalRepond/datakult/commit/09e02f542f982b4b059a8f27c1c75b9d53fba5ed))

- Fix ghcr.io username in docker-compose
  ([`a4f2032`](https://github.com/PascalRepond/datakult/commit/a4f2032b72baada177ee2bdd3006abb066eef1ab))

### Chores

- Add automatic release workflow
  ([`a194383`](https://github.com/PascalRepond/datakult/commit/a19438303c905937561b0d2932c5d48c4c8cd464))

- Consolidate tests
  ([`0917cc2`](https://github.com/PascalRepond/datakult/commit/0917cc2c621dafbc1fab648bf0bc931aea36dc2e))

- Enhance and harmonise media and profile forms
  ([`a17880b`](https://github.com/PascalRepond/datakult/commit/a17880bbdefd56e884abc06066ba690b704e9451))

### Features

- Add backup management
  ([`0e25398`](https://github.com/PascalRepond/datakult/commit/0e25398adf5ec803aba45d7ebfb46bc7d43a556e))

- Add cover image input to media edit template
  ([`ddda38f`](https://github.com/PascalRepond/datakult/commit/ddda38f852d328ea80341c233b3e8ca0e03fc453))

- Add external_uri field to Media
  ([`0d74989`](https://github.com/PascalRepond/datakult/commit/0d74989a20464cc4b1d00f116bf729820bc113b5))

- Add lazy loading for media list
  ([`0b0747a`](https://github.com/PascalRepond/datakult/commit/0b0747ad67ef327515d21c5881f758055406c7a7))

- Add rendered markdown field for media review display
  ([`13b2c69`](https://github.com/PascalRepond/datakult/commit/13b2c69e25bacafd753ad7613eeccb3ab349e357))

- Add user profile editing functionality
  ([`426b132`](https://github.com/PascalRepond/datakult/commit/426b13287ed8886bffc5d90f5c598794c50d837b))

- Implement inline-editable fields and star rating widget
  ([`45f9d0f`](https://github.com/PascalRepond/datakult/commit/45f9d0fc8864f117a0f9cba67639cf6c72d292ce))

### Refactoring

- **media-list**: Enhance media list layout
  ([`2296e0f`](https://github.com/PascalRepond/datakult/commit/2296e0f999aadf1766b7be4ea50c47af7716220e))


## v0.1.0 (2025-12-24)

- Initial Release
