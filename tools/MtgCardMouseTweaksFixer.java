import java.io.IOException;
import java.lang.classfile.ClassFile;
import java.lang.classfile.MethodModel;
import java.lang.classfile.instruction.InvokeInstruction;
import java.lang.constant.ClassDesc;
import java.lang.constant.MethodTypeDesc;
import java.lang.reflect.Modifier;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

/**
 * Standalone Java 25 application: locally patches MTGCard's optional Mouse Tweaks
 * mixin plugin to probe for class resources WITHOUT loading the target class.
 *
 * This fixes the premature target load while preserving Mouse Tweaks and MTGCard's
 * special slot handling. No MTGCard binaries are distributed with this tool.
 */
public final class MtgCardMouseTweaksFixer {
    private static final String CLASS_NAME =
        "com/spider/mtgcard/client/compat/mousetweaks/MouseTweaksCompatMixinPlugin.class";
    private static final String PLUGIN =
        "com.spider.mtgcard.client.compat.mousetweaks.MouseTweaksCompatMixinPlugin";
    private static final String CONFIG = "mtgcard.client.mixins.json";
    private static final String TARGET = "MouseTweaksGuiContainerHandlerMixin";

    private static final ClassDesc STRING = ClassDesc.of("java.lang.String");
    private static final ClassDesc CLASS = ClassDesc.of("java.lang.Class");
    private static final ClassDesc LOADER = ClassDesc.of("java.lang.ClassLoader");
    private static final ClassDesc OBJECTS = ClassDesc.of("java.util.Objects");
    private static final ClassDesc OBJECT = ClassDesc.of("java.lang.Object");
    private static final ClassDesc CHAR = java.lang.constant.ConstantDescs.CD_char;
    private static final ClassDesc BOOLEAN = java.lang.constant.ConstantDescs.CD_boolean;
    private static final ClassDesc URL = ClassDesc.of("java.net.URL");
    private static final ClassDesc SELF = ClassDesc.of(PLUGIN);

    private MtgCardMouseTweaksFixer() {}

    private static boolean isOldProbe(MethodModel method) {
        return method.code().orElseThrow().elementStream().anyMatch(element ->
            element instanceof InvokeInstruction call
                && call.owner().name().equalsString("java/lang/Class")
                && call.name().equalsString("forName"));
    }

    /** Substitute a resource lookup for the dangerous Class.forName(name,false,loader). */
    static byte[] patchClass(byte[] original) {
        ClassFile classfile = ClassFile.of();
        var model = classfile.parse(original);
        if (!model.thisClass().asInternalName().equals(CLASS_NAME.substring(0, CLASS_NAME.length() - 6))) {
            throw new IllegalArgumentException("Unexpected plugin class");
        }
        var methods = model.methods().stream()
            .filter(m -> m.methodName().equalsString("isClassPresent")
                && m.methodType().equalsString("(Ljava/lang/String;)Z"))
            .toList();
        if (methods.size() != 1 || !isOldProbe(methods.getFirst())) {
            throw new IllegalArgumentException("Unsupported or already-fixed plugin; refusing to patch");
        }
        return classfile.transformClass(model, (builder, element) -> {
            if (element instanceof MethodModel method
                    && method.methodName().equalsString("isClassPresent")
                    && method.methodType().equalsString("(Ljava/lang/String;)Z")) {
                builder.withMethodBody("isClassPresent",
                    MethodTypeDesc.of(BOOLEAN, STRING),
                    Modifier.PRIVATE | Modifier.STATIC,
                    code -> {
                        // Convert package.name.Class to package/name/Class.class
                        code.aload(0);
                        code.ldc(".");
                        code.ldc("/");
                        code.invokevirtual(STRING, "replace",
                            MethodTypeDesc.of(STRING, STRING, STRING));
                        code.ldc(".class");
                        code.invokevirtual(STRING, "concat",
                            MethodTypeDesc.of(STRING, STRING));
                        // Use the plugin's Knot classloader so mod resources can be found.
                        code.ldc(SELF);
                        code.invokevirtual(CLASS, "getClassLoader",
                            MethodTypeDesc.of(LOADER));
                        code.swap();
                        code.invokevirtual(LOADER, "getResource",
                            MethodTypeDesc.of(URL, STRING));
                        code.invokestatic(OBJECTS, "nonNull",
                            MethodTypeDesc.of(BOOLEAN, OBJECT));
                        code.ireturn();
                    });
            } else {
                builder.with(element);
            }
        });
    }

    private static byte[] required(ZipFile jar, String path) throws IOException {
        var item = jar.getEntry(path);
        if (item == null) throw new IllegalArgumentException("MTGCard JAR is missing " + path);
        try (var stream = jar.getInputStream(item)) {
            return stream.readAllBytes();
        }
    }

    static void patch(Path original, Path output) throws IOException {
        if (!Files.isRegularFile(original)) throw new IllegalArgumentException("MTGCard input JAR does not exist");
        if (original.toAbsolutePath().normalize().equals(output.toAbsolutePath().normalize())) {
            throw new IllegalArgumentException("The original MTGCard JAR will not be overwritten");
        }
        if (Files.exists(output)) throw new IllegalArgumentException("Output exists; refusing overwrite: " + output);
        byte[] updatedClass;
        try (var jar = new ZipFile(original.toFile())) {
            String manifest = new String(required(jar, "fabric.mod.json"), StandardCharsets.UTF_8);
            String compat = new String(required(jar, CONFIG), StandardCharsets.UTF_8);
            if (!manifest.matches("(?s).*\\\"id\\\"\\s*:\\s*\\\"mtgcard\\\".*")
                || !manifest.contains(CONFIG) || !compat.contains(PLUGIN) || !compat.contains(TARGET)) {
                throw new IllegalArgumentException("This isn't the expected MTGCard Fabric compatibility configuration");
            }
            if (jar.getEntry("META-INF/MANIFEST.MF") != null) {
                // Binary-signature entries would be invalidated by class changes.
                var names = jar.entries();
                while (names.hasMoreElements()) {
                    String name = names.nextElement().getName().toUpperCase(java.util.Locale.ROOT);
                    if (name.startsWith("META-INF/") && (name.endsWith(".SF")
                            || name.endsWith(".DSA") || name.endsWith(".RSA") || name.endsWith(".EC"))) {
                        throw new IllegalArgumentException("Signed JAR cannot safely be modified");
                    }
                }
            }
            updatedClass = patchClass(required(jar, CLASS_NAME));
            // Ensure the patched method is valid bytecode and no longer calls Class.forName.
            var patchedModel = ClassFile.of().parse(updatedClass);
            var method = patchedModel.methods().stream()
                .filter(m -> m.methodName().equalsString("isClassPresent")).findFirst().orElseThrow();
            if (isOldProbe(method)) throw new IllegalStateException("Premature class-loading probe remains");

            Set<String> entries = new HashSet<>();
            var names = jar.entries();
            while (names.hasMoreElements()) {
                if (!entries.add(names.nextElement().getName())) {
                    throw new IllegalArgumentException("Duplicate entries in original JAR");
                }
            }
            Path parent = output.toAbsolutePath().getParent();
            Files.createDirectories(parent);
            Path temp = Files.createTempFile(parent, "mtgcard-mixin-fix-", ".tmp");
            boolean completed = false;
            try {
                try (var out = new ZipOutputStream(Files.newOutputStream(temp))) {
                    var walk = jar.entries();
                    while (walk.hasMoreElements()) {
                        var entry = walk.nextElement();
                        var next = new ZipEntry(entry.getName());
                        if (entry.getTime() != -1) next.setTime(entry.getTime());
                        if (entry.getComment() != null) next.setComment(entry.getComment());
                        out.putNextEntry(next);
                        if (!entry.isDirectory()) {
                            if (entry.getName().equals(CLASS_NAME)) {
                                out.write(updatedClass);
                            } else {
                                try (var input = jar.getInputStream(entry)) {
                                    input.transferTo(out);
                                }
                            }
                        }
                        out.closeEntry();
                    }
                }
                try (var check = new ZipFile(temp.toFile())) {
                    var before = jar.entries();
                    while (before.hasMoreElements()) {
                        var entry = before.nextElement();
                        if (!entry.isDirectory() && !entry.getName().equals(CLASS_NAME)) {
                            if (!java.util.Arrays.equals(required(jar, entry.getName()), required(check, entry.getName()))) {
                                throw new IllegalStateException("Unrelated file changed: " + entry.getName());
                            }
                        }
                    }
                }
                Files.move(temp, output); // no REPLACE_EXISTING, by design
                completed = true;
            } finally {
                if (!completed) Files.deleteIfExists(temp);
            }
        }
    }

    public static void main(String[] args) {
        try {
            Path source;
            if (args.length == 1) {
                source = Path.of(args[0]);
            } else if (args.length == 0) {
                var chooser = new javax.swing.JFileChooser();
                chooser.setDialogTitle("Select your original MTGCard Fabric 1.7.0-26.2 JAR");
                chooser.setFileFilter(new javax.swing.filechooser.FileNameExtensionFilter("Minecraft mod JARs", "jar"));
                if (chooser.showOpenDialog(null) != javax.swing.JFileChooser.APPROVE_OPTION) return;
                source = chooser.getSelectedFile().toPath();
            } else {
                throw new IllegalArgumentException("Usage: java -jar mtgcard-mousetweaks-fixer.jar [original-mtgcard.jar]");
            }
            String oldName = source.getFileName().toString();
            if (!oldName.endsWith(".jar")) throw new IllegalArgumentException("Expected a .jar file");
            Path output = source.resolveSibling(oldName.substring(0, oldName.length() - 4) + "-earlyload-fixed.jar");
            patch(source, output);
            String message = "Created: " + output + "\n" +
                "Move original MTGCard JAR OUT of the mods folder, then install the fixed copy.\n" +
                "Mouse Tweaks compatibility remains enabled. Back up the original.";
            System.out.println(message);
            if (args.length == 0) javax.swing.JOptionPane.showMessageDialog(null, message);
        } catch (Exception exc) {
            String error = "Patch failed: " + exc.getMessage();
            System.err.println(error);
            if (args.length == 0) javax.swing.JOptionPane.showMessageDialog(null, error,
                "MTGCard Fixer", javax.swing.JOptionPane.ERROR_MESSAGE);
            System.exit(1);
        }
    }
}
