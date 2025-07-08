from werkzeug.security import generate_password_hash

password = 'admin'  # Tu peux changer ici le mot de passe que tu veux utiliser
hash = generate_password_hash(password)
print("Hash généré :", hash)
