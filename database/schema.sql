CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    u_password VARCHAR(255) NOT NULL,
    phone VARCHAR(15),
    email VARCHAR(50) UNIQUE,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tokens (
    token_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    token_number INT,
    status ENUM('waiting', 'called', 'done', 'missed') DEFAULT 'waiting',
    issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    called_at TIMESTAMP NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE queue_snapshots (
    snapshot_id INT AUTO_INCREMENT PRIMARY KEY,
    snapshot_data JSON NOT NULL, -- Save full queue state
    taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE admins (
    admin_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    a_password VARCHAR(255) NOT NULL
);

CREATE TABLE notifications (
    notif_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    token_id INT,
    notification_type ENUM('SMS', 'WhatsApp'),
    n_sent BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMP NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (token_id) REFERENCES tokens(token_id)
);
