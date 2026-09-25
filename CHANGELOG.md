# CHANGELOG

<!-- version list -->

## v1.10.1 (2026-09-25)

### Bug Fixes

- Run base.js once and quiet the tooling
  ([`4607b6b`](https://github.com/PascalRepond/datakult/commit/4607b6b82a3b044397736756bdbadb640a7c1d31))

- **backup**: Report a backup with an invalid dump
  ([`12cd5ee`](https://github.com/PascalRepond/datakult/commit/12cd5eeea7588cfa4aa655d40f60b751fdaaa6fc))

- **backup**: Stop losing data and leaving files
  ([`4ef0231`](https://github.com/PascalRepond/datakult/commit/4ef02310548e9d641115bb286c60a579ce141f38))

- **i18n**: Translate the texts left in English
  ([`4557a2f`](https://github.com/PascalRepond/datakult/commit/4557a2f29430c93dff981caa7e81ba410a9fcfd5))

- **import**: Report API failures safely and once
  ([`00a436a`](https://github.com/PascalRepond/datakult/commit/00a436aeb089e14dda922be84f2c2462a334f6b5))

- **models**: Reject images of too many pixels
  ([`4faa72b`](https://github.com/PascalRepond/datakult/commit/4faa72b9853afa885c74504ef766ff4328bed58f))

- **ui**: Confirm view deletions in a dialog
  ([`8696695`](https://github.com/PascalRepond/datakult/commit/869669560512d87b0369a899dbe6b89d7ea33df4))

- **ui**: Dismiss the toasts of boosted pages
  ([`2762e29`](https://github.com/PascalRepond/datakult/commit/2762e2969d3527d063239d9666e0ef92c25668c9))

- **ui**: Keep closed dropdown menus off the page
  ([`f9d48f4`](https://github.com/PascalRepond/datakult/commit/f9d48f44dee2288c92573c0e8ee2d2863107def1))

- **ui**: Repair the cover field, date and URLs
  ([`602b6e6`](https://github.com/PascalRepond/datakult/commit/602b6e6965da16631e56ad9403689a6f0b6883d1))

- **ui**: Search as typed or pasted after 300 ms
  ([`290ffd7`](https://github.com/PascalRepond/datakult/commit/290ffd7d23df2a1402fe9cd91965a48736e5af68))

- **views**: Pick suggested chips by POST only
  ([`1b8804b`](https://github.com/PascalRepond/datakult/commit/1b8804bd1b029765b90ec36ea9acbcfcc8d072bf))

### Chores

- Update dependencies
  ([`b7f4192`](https://github.com/PascalRepond/datakult/commit/b7f41925ee8d70bc3c087312ca0cdeed0dcac3d9))

### Code Style

- Replace em-dash by `|` in titles
  ([`2dbeeda`](https://github.com/PascalRepond/datakult/commit/2dbeeda77b13bed581e2c3c922ed1da78a4be0f0))

### Continuous Integration

- Compile the translations before the tests
  ([`0b2d772`](https://github.com/PascalRepond/datakult/commit/0b2d772bb37bf22ac00b0dc6e65c69dd4ea2f4fc))

### Performance Improvements

- Disable image lazy loading
  ([`e6a7a65`](https://github.com/PascalRepond/datakult/commit/e6a7a65deaab8f04613c523c30e06284aa7c136b))

### Refactoring

- **forms**: Share the live field validation
  ([`a2e3e2f`](https://github.com/PascalRepond/datakult/commit/a2e3e2f9633ca91f1ff13458c1490d0db2576b11))

- **models**: Name choices and share fields
  ([`cb251c1`](https://github.com/PascalRepond/datakult/commit/cb251c1b0bb2279b190bc60ac1e0dcfbc2eb997d))

- **services**: Share a client between APIs
  ([`5afa13b`](https://github.com/PascalRepond/datakult/commit/5afa13bdc7f86770e64746557489ec2c6695d49c))

- **ui**: Apply the theme by data-theme only
  ([`8324dcc`](https://github.com/PascalRepond/datakult/commit/8324dccb5aecf45bdd88d0da2e4136b948cff1e7))

- **ui**: Open the modals as dialogs
  ([`23cd372`](https://github.com/PascalRepond/datakult/commit/23cd3722e0773af3c6dc6c864b7f55d29899aeca))

- **ui**: Share markup repeated by templates
  ([`bb6c853`](https://github.com/PascalRepond/datakult/commit/bb6c8531b13e9751013a0ccfbf29b2cbb9f2f9b5))

- **views**: Split views into domain modules
  ([`dc82ab6`](https://github.com/PascalRepond/datakult/commit/dc82ab6c9c188e85b79d3c0bd99bcac740e8d231))

### Testing

- Expect the new separator of page titles
  ([`195aa99`](https://github.com/PascalRepond/datakult/commit/195aa995681541cd5a6396e9485ffc7ecd2bfe82))

- Isolate media files and speed up the suite
  ([`aa3a465`](https://github.com/PascalRepond/datakult/commit/aa3a46587416e520fc68d76aa232732f756fe51d))

- Prune redundant tests and share fixtures
  ([`e6d3d2a`](https://github.com/PascalRepond/datakult/commit/e6d3d2a3c1b37b6f8b568f9d3840a67ed4949921))


## v1.10.0 (2026-09-25)

### Bug Fixes

- **import**: Compress imported covers
  ([`e1e6b38`](https://github.com/PascalRepond/datakult/commit/e1e6b38af6ca4afb8c675a9d617221e41675361e))

### Features

- **ui**: Add sidebar shortcuts by media type
  ([`96d65a6`](https://github.com/PascalRepond/datakult/commit/96d65a6ec9b21bf31bbd9e5bb56b42e535915d72))

- **ui**: Open statistics on the current year
  ([`f2f07b2`](https://github.com/PascalRepond/datakult/commit/f2f07b29971884d57b3bd28952216ebda98582e7))

### Performance Improvements

- **ui**: Colour cover frames instead of blurring
  ([`082df7b`](https://github.com/PascalRepond/datakult/commit/082df7b721dacfdda5ee0f8123b80c8eafde95e6))


## v1.9.1 (2026-09-25)

### Bug Fixes

- **tests**: Check placeholders without catalogs
  ([`45b5adb`](https://github.com/PascalRepond/datakult/commit/45b5adb25745ff0745adde7afdb21bbc5ee1ea9c))


## v1.9.0 (2026-09-25)

### Bug Fixes

- **import**: Search Google Books with an API key
  ([`2475b58`](https://github.com/PascalRepond/datakult/commit/2475b581bf1de1f3114cd26b5a1da40a1788c0c8))

- **pwa**: Serve fresh pages and static files
  ([`7f649f6`](https://github.com/PascalRepond/datakult/commit/7f649f67564cd62a9e707625e48f2087378a27ae))

- **tests**: Reset the language after each test
  ([`4e5748a`](https://github.com/PascalRepond/datakult/commit/4e5748adb19deaa23ef90d0724e1265c64150e6a))

- **theme**: Raise colour contrast to WCAG AA
  ([`740dace`](https://github.com/PascalRepond/datakult/commit/740dace244f31220d610bca61ca1b7a09e343f34))

- **ui**: Fix bugs found in the UI/UX review
  ([`1d80db0`](https://github.com/PascalRepond/datakult/commit/1d80db06245a83b8ce403ba98067f7cfb889e9be))

### Documentation

- Keep only non-derivable rules in CLAUDE.md
  ([`b4d0f84`](https://github.com/PascalRepond/datakult/commit/b4d0f845edde71fa94ba794b7d7a24ce4b630f5d))

### Features

- **detail**: Invite to rate and review media
  ([`9f63191`](https://github.com/PascalRepond/datakult/commit/9f631919fe47238cc776374bf81a0ad1a0c98a4c))

- **edit**: Keep form actions at hand
  ([`71b80d8`](https://github.com/PascalRepond/datakult/commit/71b80d8b3671a4ba524f2b1c5d5907a6a5bad0cb))

- **filters**: Apply filters as they change
  ([`6216c9d`](https://github.com/PascalRepond/datakult/commit/6216c9dfd25661d484480e510679917167add8e8))

- **import**: Search every source from one field
  ([`ed85817`](https://github.com/PascalRepond/datakult/commit/ed85817d07d52628b2dc51057d4f116ef01cd1ad))

- **list**: Link to the rest of long reviews
  ([`ecc52e5`](https://github.com/PascalRepond/datakult/commit/ecc52e577ab3173a53e708ad5dd1c14b8c8ed466))

- **list**: Read reviews in a modal
  ([`bcc3cec`](https://github.com/PascalRepond/datakult/commit/bcc3cecdd7c13c42f9b14f03628699d61fff7451))

- **list**: Refine the media cards
  ([`b88c6c8`](https://github.com/PascalRepond/datakult/commit/b88c6c8fd80f8b23cf10c56c2dc35ba8b0004c67))

- **list**: Show scores over the covers
  ([`0c24877`](https://github.com/PascalRepond/datakult/commit/0c24877aa73210791ddeb08db8f3cf85712cc9c6))

- **nav**: Make adding and navigating quicker
  ([`1446413`](https://github.com/PascalRepond/datakult/commit/14464137fb468d01a1c47dd5b2f2bc1e390e5b06))

- **ui**: Colour appreciated scores in green
  ([`8f25d00`](https://github.com/PascalRepond/datakult/commit/8f25d005808ee0e9325eb620e7f830397661975c))

- **ui**: Join scores and their verdicts
  ([`8cf36dd`](https://github.com/PascalRepond/datakult/commit/8cf36ddb51437d75454479db50b79f45214087ae))

- **ui**: Keep score rings neutral inside
  ([`ac660a8`](https://github.com/PascalRepond/datakult/commit/ac660a8373e46c5425b7f4f2b1d64a5e3ed3c8da))

- **ui**: Make the interface consistent
  ([`54a2aa2`](https://github.com/PascalRepond/datakult/commit/54a2aa246405ebc01527e6208fb3ecdc83f5f53a))

### Refactoring

- **backup**: Drop the inline page scripts
  ([`b3eea5e`](https://github.com/PascalRepond/datakult/commit/b3eea5e90c5693827c1366bba1349b4879b365f7))

- **edit**: Serve the cover widget script
  ([`1408ea3`](https://github.com/PascalRepond/datakult/commit/1408ea3e1495154eff4c554d1204620129d3950e))

- **import**: Share one results template
  ([`bd37a60`](https://github.com/PascalRepond/datakult/commit/bd37a60506692bebd6f9826ce02ad16b7da333ca))

- **list**: Drop the list view
  ([`b24cbf7`](https://github.com/PascalRepond/datakult/commit/b24cbf7370f13d1b9519b19d19408e1cf182897e))


## v1.8.0 (2026-09-23)

### Bug Fixes

- **filters**: Include partial dates on start day
  ([`0b601a7`](https://github.com/PascalRepond/datakult/commit/0b601a77a3b47ecb5fffbc4579e0f829630482fc))

- **tests**: Keep backups out of src/ and narrow Tailwind watch sources
  ([`a28e547`](https://github.com/PascalRepond/datakult/commit/a28e5473ef0e803a55f37135e991e24760156624))

### Build System

- Update dependencies
  ([`f99a00c`](https://github.com/PascalRepond/datakult/commit/f99a00c1be3e6002c8eb71aef4f9ddd6530e303e))

### Chores

- Bump actions/setup-node in the github-actions group
  ([`7ce6f3c`](https://github.com/PascalRepond/datakult/commit/7ce6f3cfe8044cc8126f62a71614f164cba0a446))

- Bump gitpython from 3.1.50 to 3.1.52
  ([`6b7bf5f`](https://github.com/PascalRepond/datakult/commit/6b7bf5f4ca9db71462e705a8d1cb178e348d8efa))

- Bump gitpython from 3.1.52 to 3.1.59
  ([`984569c`](https://github.com/PascalRepond/datakult/commit/984569c6b0b53a14cf47edd795a55c0f5f32b4da))

- Bump pip from 26.1.2 to 26.2
  ([`c1019e5`](https://github.com/PascalRepond/datakult/commit/c1019e568fbd26b44f6401a05141d0d61bb59453))

- Bump postcss from 8.5.16 to 8.5.25 in /src/theme/static_src
  ([`d2fc075`](https://github.com/PascalRepond/datakult/commit/d2fc0755612ba731fda6ed3db1f2bb412b84cc62))

- Bump sqlparse from 0.5.5 to 0.6.0
  ([`0af4088`](https://github.com/PascalRepond/datakult/commit/0af4088b332176384a0df8af2c7281a080e72a1e))

- Bump the github-actions group across 1 directory with 3 updates
  ([`0f57fc9`](https://github.com/PascalRepond/datakult/commit/0f57fc9c4af045ee33eec15a9842e9082e6684d6))

- Bump the github-actions group with 2 updates
  ([`3129633`](https://github.com/PascalRepond/datakult/commit/31296337b2b99a2d5fc52f63acf241ec7e70dc84))

- Enhance Claude guidelines
  ([`4e57764`](https://github.com/PascalRepond/datakult/commit/4e57764de9635218c155994124a724cae0ea67d0))

- Update dependencies
  ([`0646fec`](https://github.com/PascalRepond/datakult/commit/0646fec1e2bbf160c34017db054b9048c0b1bf9e))

### Documentation

- **readme**: Fix wrong node version
  ([`ab67d35`](https://github.com/PascalRepond/datakult/commit/ab67d35fc3636a9d9663a182e740ff7dcc989477))

### Features

- **stats**: Add a statistics dashboard
  ([`fc6b54f`](https://github.com/PascalRepond/datakult/commit/fc6b54fbef04266e718c93aa6ef8cc25ec2b9973))

### Refactoring

- Clean up readability
  ([`0e8badb`](https://github.com/PascalRepond/datakult/commit/0e8badbae717d9da3d3753eb8f204bf2ae87c7ec))


## v1.7.1 (2026-06-03)

### Chores

- Update dependencies
  ([`6e95bc4`](https://github.com/PascalRepond/datakult/commit/6e95bc413f25e2d2350cc10934f04927703c5e12))

- Update dependencies and improve project config
  ([`357e7d4`](https://github.com/PascalRepond/datakult/commit/357e7d4c2f9b079b037d233615bca4cb93bf5062))


## v1.7.0 (2026-04-27)

### Chores

- Update dependencies
  ([`d989d59`](https://github.com/PascalRepond/datakult/commit/d989d59a54524583aad225cc9f1a644606cc78a7))

### Features

- **import**: Add Google Books as complementary book source
  ([`5d5bf89`](https://github.com/PascalRepond/datakult/commit/5d5bf89c95503225359b90ef2ea0e52666f154d4))


## v1.6.3 (2026-04-14)

### Chores

- Update dependencies and Node/Python versions
  ([`a4511d4`](https://github.com/PascalRepond/datakult/commit/a4511d40228a5808d858f28351d2617237fa23c8))

### Continuous Integration

- Update github actions versions to latest
  ([`22c629c`](https://github.com/PascalRepond/datakult/commit/22c629cef2015453b860456107c520089af6c88a))

### Refactoring

- **tests**: Replace class-based tests with plain functions
  ([`5b251c1`](https://github.com/PascalRepond/datakult/commit/5b251c1db8862655828fc6a79dfa644c210621fe))


## v1.6.2 (2026-03-21)

### Bug Fixes

- **editor**: Allow browser spell check in markdown editor
  ([`202a76b`](https://github.com/PascalRepond/datakult/commit/202a76b4dfa4909221e172cfb58540719a4c495d))


## v1.6.1 (2026-02-28)

### Bug Fixes

- Display review date even if no review
  ([`d782240`](https://github.com/PascalRepond/datakult/commit/d78224095de09fabe404ef35dc3ec23888924bfb))

### Chores

- Update dependencies
  ([`ef383f9`](https://github.com/PascalRepond/datakult/commit/ef383f96a33bc71ee4b1def91d716db3b8546a44))

- Update dependencies
  ([`ef6ddab`](https://github.com/PascalRepond/datakult/commit/ef6ddab84a6584fdbb8b4914c1517a4a774c176b))


## v1.6.0 (2026-01-21)

### Bug Fixes

- Display saved views in the sidebar on all pages
  ([`a6dcbb1`](https://github.com/PascalRepond/datakult/commit/a6dcbb1672646cab1e78bf9946b4ca305e0df1f9))

### Chores

- Update translations
  ([`1023487`](https://github.com/PascalRepond/datakult/commit/102348789334dfd6cc53092be9d9128b26c9108e))

### Features

- Add musicbrainz metadata import
  ([`b74c549`](https://github.com/PascalRepond/datakult/commit/b74c549165a7c0dfe82a54c5e631c00c10fe667f))

- Importing from an existing media opens the correct tab and pre-fills the search
  ([`8054eaf`](https://github.com/PascalRepond/datakult/commit/8054eaf1e6369445afe268883988a5f097fea241))

### Testing

- Add tests for latest features
  ([`b013b4f`](https://github.com/PascalRepond/datakult/commit/b013b4f9dc72993e209f06f2cfcf6528e50ea3d8))


## v1.5.0 (2026-01-21)

### Features

- Add basic PWA support
  ([`2082d6d`](https://github.com/PascalRepond/datakult/commit/2082d6d3517ccce3b27881b87280fba0fed3f06a))

- Add igdb and openlibrary imports
  ([`5a45e37`](https://github.com/PascalRepond/datakult/commit/5a45e37ab066951a5a64e17d11c44834d32a97c9))

- Add tags system and TMDB import integration
  ([`59a4e82`](https://github.com/PascalRepond/datakult/commit/59a4e8286c546ac17cc3a0481cd13a8c537d22f0))


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
