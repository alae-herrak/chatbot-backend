import argostranslate.package

argostranslate.package.update_package_index()
available = argostranslate.package.get_available_packages()

for p in available:
    print(f"{p.from_code} → {p.to_code}")
